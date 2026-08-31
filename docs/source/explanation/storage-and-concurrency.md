# Storage and concurrency

exporgo stores a study's bulk data as plain Parquet files with a small catalog on top, and it
never runs a server. That choice is deliberate, and it shapes both what exporgo is fast at and
how it behaves when several people hit the same study at once. This page explains the model,
the concurrency guarantee it can honestly make, and why it isn't a database.

## The storage model: a data lake, in miniature

A store is a **data-lake table**, not a database table:

- **Immutable data files.** Every write drops new `part-<uuid>.parquet` fragments, Hive-
  partitioned on the identity keys. Files are write-once and uniquely named, so two writes
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
which is itself a store — so the array store inherits the immutable-files-plus-append-only-catalog
shape, and the concurrency guarantees below, unchanged.

## What exporgo is good at

The plain-files model buys real strengths:

- **Fast, out-of-core reads.** {meth}`~exporgo.datastore.Store.scan` returns a lazy polars
  `LazyFrame` over the Parquet fragments. Filters on the partition keys prune whole folders,
  row-group statistics prune within a file, and nothing is read until you collect — so a
  selective query over a large store touches only the fragments it needs, and never loads more
  than it must.
- **No server, no service.** A study is a directory. You can put it on a laptop, a lab NAS, or
  cloud object storage and it works the same way, with nothing to install, run, or keep alive.
- **The filesystem is the source of truth.** exporgo caches no status; `validate`, `coverage`,
  and every scan re-read the tree. State can't drift out of sync with reality, and any tool —
  exporgo or not — can read the Parquet directly.

These are the properties you'd lose the moment the data moved into a database engine.

## Concurrency: the guarantee, and its honest limits

The realistic multi-user case is a study on a lab server that several members mount at once.
Here is what exporgo can promise, and what no plain file share can:

- **Disjoint writers are safe.** Two people writing different subjects (or different sessions)
  to the same store just work: distinct partitions mean distinct data files, and each write's
  manifest entry is its own file. Neither can clobber the other — there's nothing shared to
  race. This is the normal lab pattern, and it needs zero coordination.
- **Conflicts fail loud, not silent.** `write(frame, mode="unique")` refuses to add an identity
  the store already contains rather than duplicating it. exporgo's stance is to raise on a
  conflict it can see, never to quietly overwrite.
- **The true-conflict boundary.** Two writers racing the *same* identity at the *same* instant,
  or a `mode="overwrite"` of a partition someone else is writing, is the one case a bare file
  share cannot arbitrate — there is no atomic compare-and-set across NFS/SMB to lean on. exporgo
  doesn't pretend otherwise: it avoids conflicts by design and fails loudly on the ones it
  detects, and that last sliver is a genuine limit of the medium, not a bug to paper over with
  an unreliable lock.
- **Reads are eventually consistent.** Because exporgo re-reads and caches nothing, a reader
  sees a recent view of the tree — under a network filesystem's close-to-open consistency, that
  means very recent, not to-the-millisecond. That's the right guarantee for this kind of
  storage, and it's an honest one.

Deliberately, exporgo does **not** use file locking. A lock over NFS/SMB is a false comfort: it
looks safe, fails silently, and is worse than no lock because people trust it. Conflict-
avoidance by unique-name and append-only writes is both simpler and more robust.

## Why not just use a database?

"Make it a database" splits three ways, and only one keeps the strengths above:

- **Bulk data in a database (Postgres, SQLite): no — it kills the reads.** Row stores are poor
  at wide analytical scans of large arrays, which is exactly what a neural or behavioral store
  is. You'd surrender the columnar, pruned, out-of-core performance that is the whole point.
- **A database for the catalog only (SQLite): right idea, wrong deployment.** The data would
  stay Parquet (fast), and the DB would serialize only the tiny manifest updates. But SQLite
  over a network filesystem is explicitly unsafe — its locking relies on the same POSIX
  semantics NFS breaks — and a *server* database reintroduces the server dependency the whole
  design exists to avoid.
- **A lakehouse format: the closest fit — see below.**

exporgo's workload is write-once bulk data, occasional metadata declarations, and analytical
scans, with writers who own disjoint slices. That's a data-lake access pattern, not an OLTP
one. A database is the right tool when you have high-frequency concurrent mutation of shared
rows, strong cross-entity transactions, or complex indexed queries at write time — a web app,
not a study.

## The lakehouse option, explicitly

Delta Lake and Apache Iceberg are the industrial answer to "many writers to Parquet on shared
storage." They're worth naming precisely, because exporgo's append-only manifest is a
deliberate miniature of the same idea — immutable data files plus a transaction log.

**Pros:**

- **Full ACID and snapshot isolation.** A reader sees one consistent version; concurrent
  commits are serialized by the log, including safe concurrent writes to the *same* partition.
- **Keeps the read performance.** Data stays Parquet, so pruning and lazy scans are intact —
  and the log's data-skipping statistics can prune even better.
- **Time travel and schema evolution** come built in: query an old snapshot, or evolve columns
  under versioned control.

**Cons:**

- **A heavy dependency and real operational weight.** delta-rs or PyIceberg is a large addition
  to a framework whose selling point is "a study is a directory."
- **The atomic-commit guarantee needs a primitive the medium may not have.** Their isolation
  leans on an atomic put-if-absent, which object stores provide but a bare NFS/SMB share only
  approximates via atomic rename. On a plain lab server with no coordinator, even a lakehouse
  degrades toward "safe for disjoint writers, careful for concurrent same-table commits" — the
  same place the append-only manifest already sits, with a fraction of the machinery.
- **Overkill for the actual workload.** The sophistication buys safe concurrent same-partition
  commits and multi-file atomic transactions — things a disjoint-writer lab study rarely needs.

**The migration path stays open.** Today's unique-fragment manifest is a natural stepping stone,
not a dead end: if a study outgrows it — moving to cloud object storage, or genuinely needing
concurrent commits to the same partition — you can swap the catalog layer for Iceberg or Delta
with the *same Parquet files underneath*. You get the cheap, dependency-free, performance-neutral
model now, and the escape hatch later.
