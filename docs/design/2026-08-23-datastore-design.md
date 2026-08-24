# exporgo — Datastore Layer Design

*Design record, 2026-08-23. Shaped through discussion; not yet scheduled for build.*

## Context

exporgo studies need to store bulk scientific data (behavior tables, neural activity
arrays, licking traces, …) and **retrieve it rapidly via polars**, filtered by things
like group/subject/session ("give me all behavior for group X's mice"). Today this is
done ad-hoc: the `spk` package (`dariks_special`) grew an emergent "datastore" — two
Parquet datasets (`experiments/`, `neurons/`) written with pyarrow and read with polars.
Its foundation is right, but four things make it creak, and this design fixes them:

1. **No partitioning by query keys** (UUID-named, row-count-chunked fragments) → every
   query scans every file; and **no group/cohort concept** at all, so the core use case
   isn't even expressible.
2. **Large arrays stored inline** as `List(Float64)` inside the tables → bloats reads,
   defeats projection.
3. **Eager read path** fused with heavy domain transforms (`lazy=True` raises
   `NotImplementedError`).
4. **No manifest/catalog; fragile writes** (racy global ID offsets, UUID-append +
   read-time dedup, no real overwrite/atomicity).

**Goal:** a generic, domain-agnostic datastore engine that any study configures with its
own stores, giving fast partitioned polars retrieval, strict per-store schemas, and clean
write semantics.

## Where it sits: two layers, one identity vocabulary

exporgo has two data-facing layers that **click together through a single, study-level
identity vocabulary declared up front**:

| Layer | Holds | Nature |
|---|---|---|
| **Monitoring / metadata** | Study structure + identities (1–3 user-chosen keys; default `Subject`), step status, params, file locations | **Derived** metadata (status computed from the filesystem); canonical **owner of the identity vocabulary**. |
| **Datastore** | The bulk scientific data (behavior, neural, …) | **Authoritative** storage of data you dump in — *not* a derived view. Partitions on the identity vocabulary. |

The identity vocabulary is **declared once at the study level** — **1–3 keys the user
chooses, defaulting to `["Subject"]`** — and reused as the partition keys of every store,
so cross-component joins are guaranteed to line up. Monitoring defines *who/what*; the
datastore holds *the data*, keyed the same way.

## Core concepts

- **A study is a *catalog* of named component stores** — e.g. `behavior`, `neural`,
  `licking` — each an independent, partitioned Parquet dataset. Components are separate
  (not one table) because they differ in schema, key cardinality, size, and access
  pattern; arrays get their **own** store so the tabular stores stay blob-free.
- **Per store, declared up front:**
  - an **exact payload schema** (columns + dtypes), **strictly enforced on write** and
    recorded in the store's manifest;
  - **1–3 partition keys** (drawn from the shared identity vocabulary + optionally a
    low-cardinality store-specific column like `condition`);
  - an **optional sort column** (a high-cardinality range axis like `trial`/`time`).
- **Strict *within* a store, flexible *across* stores.** Each store's schema is fixed and
  enforced; different stores (and different studies) have entirely different schemas. That
  per-store flexibility is what covers "every study is different."

## Partitioning model (the retrieval engine)

Partition keys become the **directory layout** (Hive-style); the folders *are* a physical
index:

```
study_root/
  study.toml                         # study declaration: identity keys, resources, store specs (keys, sort col)
  behavior/  _schema.parquet  _manifest.json  group=cms/subject=m10/session=1/part-*.parquet
  neural/    _schema.parquet  _manifest.json  subject=m10/session=1/part-*.parquet
  licking/   _schema.parquet  _manifest.json  subject=m10/session=1/part-*.parquet
```

*(As built: each store's schema is persisted losslessly as a 0-row `_schema.parquet`
anchor and its fragment inventory in `_manifest.json`; the study-level catalog is
`study.toml`, not a separate `catalog.json`.)*

Retrieval is **one lazy polars query**, no manual iteration:

```python
(study.store("behavior").scan()           # pl.scan_parquet(root, hive_partitioning=True)
   .filter(pl.col("group") == "cms")      # partition key   → prune folders
   .filter(pl.col("trial") > 42)          # sort column     → row-group stat skipping
   .select("subject", "session", "lick_rate")  # projection → read only these columns
   .collect())
```

Three pruning layers, all automatic: **partition pruning** (folders), **row-group
min/max skipping** (effective when sorted by the range column), and **projection**
(columns). Non-key columns are still filtered correctly via vectorized native scan — they
just don't prune folders.

**Keys stay few by design.** Partition keys are for coarse sharding on the 1–3 dominant
axes, *not* for every filter — each key multiplies folder count, and over-partitioning
recreates the small-files problem (aim for tens-to-hundreds of MB per leaf). Everything
else is served by the scan layer, so the key set does **not** escalate as filter needs
grow.

## Retrieval surface

**polars only** (no DuckDB). `store.scan()` returns a composable `LazyFrame`; callers add
`.filter`/`.select`/`.join`/`.group_by` and `.collect()`. Cross-component analysis joins
stores on the shared identity keys:

```python
beh = study.store("behavior").scan().filter(pl.col("group") == "cms")
neu = study.store("neural").scan()
combined = beh.join(neu, on=["subject", "session"], how="inner").collect()
```

Each side prunes independently, then joins. (A SQL/DuckDB surface was considered and
**explicitly dropped** — partition pruning + row-group stats + polars lazy pushdown cover
the access patterns without another dependency. It can be reconsidered later if genuinely
many-dimensional ad-hoc analytics ever demand it.)

## Write semantics (to finalize at build)

- **Validate/cast to the declared schema on write; reject mismatches loudly** (never
  silently write a drifting fragment).
- **Overwrite/append *by key*** with real replacement semantics (a re-written
  `(subject, session)` replaces that partition's fragments, not appends duplicates).
- **A manifest/catalog** as the source of truth for "what stores exist / their schemas /
  what keys are present," so existence and identity checks are O(1) rather than full-scan.
- **Versioned schema evolution**: adding a column is a deliberate, versioned migration
  (bump store version, backfill/default old fragments) — never a side effect of a write.
- Atomicity/locking for parallel per-subject writers.

## Packaging & dependencies

An opt-in extra, `exporgo[datastore]`, pulling **polars, pyarrow, numpy** (and **pydantic**
via `exporgo[study]`). The **base install** is loguru + polars (polars was promoted to base).
Domain libraries (pynapple, suite2p, regions, …) stay out of the store layer entirely — the
engine is generic; schemas are supplied by the study.

**Append uses pyarrow (not polars-native).** polars' `write_parquet(partition_by=...)` writes
one fixed-named file per partition and **clobbers** on re-write (proven: two writes to the
same partition lose the first), so it cannot append. `Store.write` uses
`pyarrow.dataset.write_dataset(existing_data_behavior="overwrite_or_ignore")` with a unique
per-write `basename_template` — an **out-of-core append** (unique fragment per write, never
reads existing data). `Store.scan` stays native polars (`scan_parquet(hive_partitioning=True)`).
**pyarrow is pinned `==24.0.0`:** 25.0.1's `_compute.pyd` is blocked by Windows Smart App
Control on the dev machine (logged in Event Viewer → CodeIntegrity, not Defender Protection
History); 24.0.0 is trusted and loads.

**Build status (2026-08-23):** MVP built & verified (TDD, 28 datastore tests) — `StoreSpec`,
`Store` (schema-enforced `write` with **append / overwrite-by-key** + pruning `scan` +
**per-store manifest**), and `study.declare_store()` / `study.store()` with catalog
persistence. The **manifest** (`<store>/_manifest.json`) records each written fragment
(path, partition, rows, timestamp) and exposes `partitions()` / `row_count()` — O(1)
"what's in here" without scanning the data. **Overwrite-by-key** (`write(frame,
mode="overwrite")`) uses the manifest to delete the incoming partitions' fragments (files +
entries) before writing, replacing only those partitions.

**Schema = real polars dtypes (no whitelist).** `StoreSpec.columns` maps names to actual
polars dtypes at full fidelity — exact int/float widths (`UInt16`, `Float32`), `List`/
`Array`/`Struct`, temporal, etc. — so **array/list columns work** (e.g. neural activity as
`pl.List(pl.Float64)`, verified end-to-end). Nested dtypes are rejected as partition/sort
keys. The schema is persisted **losslessly** as a 0-row `_schema.parquet` anchor per store
(Parquet is the serializer — no dtype string-parsing/`eval`); `study.toml` holds only each
store's name/partition-keys/sort-column. Data fragments are globbed as `part-*.parquet` so
the anchor/manifest don't interfere with scans. Deferred: schema versioning/migration.

## Sequencing

The datastore partitions on the **shared identity vocabulary**, which is monitoring's to
define. So the **identity model is the foundation of both layers** and should be designed
first (or as the first slice of the monitoring layer). The datastore is not buildable in
isolation — its keys come from there.

**Update:** that foundation is now designed — see
`docs/design/2026-08-23-study-identity-design.md` (the Study & Identity model). A store's
partition keys default to the study's identity keys, and `Identity.as_path()` is the
partition path.

## What to keep from spk / what to fix

- **Keep:** polars + Parquet + pyarrow spine; explicit centralized schemas enforced at
  write; the split by cardinality (session-level vs unit-level); the lazy pushdown reader
  pattern in `spk/rois.py::FOV.load` (`scan_parquet` + `select` + streaming collect) — the
  template to generalize.
- **Fix:** partition by real query keys + first-class shared identity; arrays in their own
  store; lazy pushdown as the *only* read path returning composable frames; a
  manifest/catalog + real overwrite/versioning instead of UUID-append + read-time dedup;
  full decoupling from spk domain internals.

Reference (spk analysis): `spk/parameters.py` (layout/query spec), `spk/definitions.py`
(schemas), `spk/organize/aggregate.py` (writer), `spk/data.py` (eager reader),
`spk/rois.py` (the good lazy reader).

## Open / spec-level items (resolve when building)

- Store-declaration mechanism (pydantic specs in code vs. a study config file — likely
  both, mirroring exporgo's config style).
- Exact neural-array layout (Parquet `List`/array columns vs. a dedicated array format),
  and how ragged arrays are handled.
- Manifest/catalog format and the concrete write/overwrite/migration API.

## Verification (when built)

TDD as with `exporgo/log`: unit-test schema enforcement (accept/reject), partition layout
produced, pruning behavior (queries touch only expected files), lazy retrieval + joins on
shared keys, and overwrite/versioning semantics; end-to-end smoke test writing two
component stores and joining them. Must pass `ruff`/`pyrefly` and hold coverage ≥ 75%.
