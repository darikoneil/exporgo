# Storage and concurrency

exporgo stores an experiment's bulk data as plain Parquet files with a small catalog on top. It
never runs a server. That choice is deliberate, and it shapes both what exporgo is fast at and
how it behaves when several people hit the same experiment at once. This page explains the model,
the concurrency guarantee it can honestly make, and why it isn't a database.

## The storage model: a data lake, in miniature

A store is a **data-lake table**, not a database table:

- **Immutable data files.** Every write drops new `part-<uuid>-<n>.parquet` fragments,
  Hive-partitioned on the identity keys. Files are write-once and uniquely named, so two writes
  never touch the same file.
- **An append-only catalog.** The manifest is a directory, `<store>/_manifest/`, where each
  write drops its own `<uuid>.json` entry recording the fragments it added (and, for
  overwrite-by-key, the ones it tombstoned). A read aggregates the directory into one view.
  Nothing is ever read-modify-written.

The catalog mirrors the data: both avoid collisions by unique naming rather than by locking.
That single decision is what makes concurrent writers safe without a coordinator.

An **array store** is the same model with a different payload. Each identity's array is a
write-once `data-<uuid>.npy` blob, Hive-partitioned on the identity keys and recorded in the same
append-only `_manifest/` log; overwriting an identity tombstones its prior blob exactly as a
tabular overwrite does. Its coordinate vectors live in a nested tabular catalog under `_coords/`,
which is itself a store, so the array store inherits the immutable-files-plus-append-only-catalog
shape unchanged. Its concurrency story is narrower, because it has no append mode; see the
guarantees below.

## What exporgo is good at

The plain-files model buys real strengths:

- **Fast, out-of-core reads.** {meth}`~exporgo.datastore.Store.scan` returns a lazy polars
  `LazyFrame` over the Parquet fragments. Filters on the partition keys prune whole folders,
  row-group statistics prune within a file, and nothing is read until you collect. A selective
  query over a large store touches only the fragments it needs, and never loads more than it
  must.
- **No server, no service.** An experiment is a directory. You can put it on a laptop or a lab
  NAS and it works the same way, with nothing to install, run, or keep alive.
- **The filesystem is the source of truth.** exporgo caches no status; `validate`, `coverage`,
  and every scan re-read the tree. State can't drift out of sync with reality, and any tool,
  exporgo or not, can read the Parquet directly.

These are the properties you'd lose the moment the data moved into a database engine.

## Concurrency: the guarantee, and its honest limits

The realistic multi-user case is an experiment on a lab server that several members mount at once.
The guarantee **depends on the write mode**, and the line between them is sharp:

- **`append` is multi-writer safe, by design.** Any number of writers may append to the same
  store, *including the same partition*, without coordination. Each write names its fragments
  with its own UUID and drops its own manifest entry, so there is no shared file to race and no
  read-modify-write anywhere in the path. This is the mode the immutable-files-plus-append-only-log
  model exists to make safe, and it is the normal lab pattern.
- **`unique` and `overwrite` need a single writer per partition.** Both are **check-then-act**:
  they read the manifest, decide, and then write. Nothing makes that pair atomic, so two writers
  aiming at the *same* partition can interleave between the check and the act — two `unique`
  writes may both pass their check and both land, and an `overwrite` may delete the fragments it
  saw while missing one that arrived in the meantime. The window is the whole operation, not an
  instant. Writers aiming at *different* partitions are unaffected, and so is any concurrent
  `append`.
- **Conflicts that can be seen fail loud.** Within a single writer, `write(frame, mode="unique")`
  refuses to add an identity the store already contains rather than duplicating it. exporgo's
  stance is to raise on a conflict it can detect, never to quietly overwrite. It just cannot
  detect one that lands during its own write.
- **The honest limit.** Making `unique` and `overwrite` safe under concurrency needs an atomic
  compare-and-set, and a bare NFS/SMB share has none to lean on. exporgo doesn't pretend
  otherwise: it makes the common mode genuinely safe, fails loudly on the conflicts it can see,
  and asks you to own a partition before you replace it. That residue is a limit of the medium,
  not a bug to paper over with an unreliable lock.
- **Reads are eventually consistent.** Because exporgo re-reads and caches nothing, a reader
  sees a recent view of the tree. Under a network filesystem's close-to-open consistency, that
  means very recent, not to-the-millisecond. That's the right guarantee for this kind of
  storage, and it's an honest one.

An **array store** sits on the stricter side of that line: it holds one array per identity, so
its only modes are `unique` and `overwrite` and both are check-then-act over the manifest. One
writer per identity. What it does guarantee is **crash safety** within a writer: an overwrite
publishes the new blob and its coordinate row, commits with the blob's manifest entry, and only
then tombstones the old pair. Coordinate rows are paired with their blob in the catalog, so a
failure at any step leaves the identity loadable with a matched array and coordinates — at worst
the previous pair, never a mismatch (see [Store arrays](../how-to/store-arrays.md)).

Deliberately, exporgo does **not** use file locking. A lock over NFS/SMB is a false comfort: it
looks safe, fails silently, and is worse than no lock because people trust it.
Conflict-avoidance by unique-name and append-only writes is simpler and harder to get wrong.

## Why not just use a database?

"Make it a database" splits three ways, and only one keeps the strengths above:

- **Bulk data in a database (Postgres, SQLite): no, it kills the reads.** Row stores are poor
  at wide analytical scans of large arrays, which is exactly what a neural or behavioral store
  is. You'd surrender the columnar, pruned, out-of-core performance that is the whole point.
- **A database for the catalog only (SQLite): right idea, wrong deployment.** The data would
  stay Parquet (fast), and the DB would serialize only the tiny manifest updates. But SQLite
  over a network filesystem is explicitly unsafe, because its locking relies on the same POSIX
  semantics NFS breaks, and a *server* database reintroduces the server dependency the whole
  design exists to avoid.
- **A lakehouse format: the closest fit.** See below.

exporgo's workload is write-once bulk data, occasional metadata declarations, and analytical
scans, with writers who own disjoint slices. That's a data-lake access pattern, not an OLTP
one. A database is the right tool when you have high-frequency concurrent mutation of shared
rows, strong cross-entity transactions, or complex indexed queries at write time: a web app,
not an experiment.

## The lakehouse option, explicitly

Delta Lake and Apache Iceberg are the industrial answer to "many writers to Parquet on shared
storage." They're worth naming precisely, because exporgo's append-only manifest is a
deliberate miniature of the same idea: immutable data files plus a transaction log.

**Pros:**

- **Full ACID and snapshot isolation.** A reader sees one consistent version; concurrent
  commits are serialized by the log, so even concurrent *replacements* of the same partition
  resolve rather than race.
- **Keeps the read performance.** Data stays Parquet, so pruning and lazy scans are intact,
  and the log's data-skipping statistics can prune even better.
- **Time travel and schema evolution** come built in: query an old snapshot, or evolve columns
  under versioned control.

**Cons:**

- **A heavy dependency and real operational weight.** delta-rs or PyIceberg is a large addition
  to a framework whose selling point is "an experiment is a directory."
- **The atomic-commit guarantee needs a primitive the medium may not have.** Their isolation
  leans on an atomic put-if-absent, which object stores provide but a bare NFS/SMB share only
  approximates via atomic rename. On a plain lab server with no coordinator, even a lakehouse
  degrades toward "safe for disjoint writers, careful for concurrent same-table commits", the
  same place the append-only manifest already sits, with a fraction of the machinery.
- **Overkill for the actual workload.** The sophistication buys atomic read-modify-write and
  multi-file transactions, things a lab experiment, whose writers append and own their
  partitions, rarely needs.

**The migration path stays open.** Today's unique-fragment manifest is a natural stepping stone,
not a dead end. Say an experiment outgrows it, by moving to cloud object storage or by genuinely
needing concurrent `unique`/`overwrite` writes to the same partition: you can swap the catalog
layer for Iceberg or Delta with the *same Parquet files underneath*. You get the cheap,
dependency-free, performance-neutral model now, and the escape hatch later.
