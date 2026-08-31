# Write to a store

A **store** is a schema-enforced, partitioned Parquet dataset exporgo owns. This guide covers
declaring one, the three write modes, and reading it back with partition pruning. It needs the
datastore extra:

```bash
uv add "exporgo[datastore]"
```

## Declare the store

Give the store a name and a polars schema: a `column → dtype` map at full fidelity (exact int
and float widths, and `List`/`Array`/`Struct` for array columns). Partition keys default to the
study's identity keys; an optional `sort_column` enables row-group range pruning:

```python
import polars as pl

study.declare_store(
    "behavior",
    {"Subject": pl.String, "Session": pl.Int64, "trial": pl.Int64, "rt": pl.Float64},
    sort_column="trial",
)
store = study.store("behavior")
```

The schema is strict and enforced on every write. A frame whose columns don't exactly match
(missing or extra) is rejected with a `ValueError`. The partition-key columns must be present in
the frame, since they drive the on-disk layout.

## Choose a write mode

{meth}`~exporgo.datastore.Store.write` takes a `mode`, and the choice is about what happens to
data already in the store:

```python
store.write(frame, mode="append")     # add new fragments (default)
store.write(frame, mode="overwrite")  # replace the partitions this frame touches
store.write(frame, mode="unique")     # refuse if any incoming identity already exists
```

- **`append`** (the default) adds fragments; a partition can gain more rows across writes. Use
  it when each write brings genuinely new rows.
- **`overwrite`** replaces, by partition: the partitions present in `frame` have their existing
  fragments deleted before the new data lands; partitions the frame doesn't mention are left
  untouched. Use it to recompute one subject's data without disturbing the rest.
- **`unique`** refuses the write, all-or-nothing, if `frame` carries any identity the store
  already contains, raising a `ValueError`. Use it to make a re-run safe against silent
  duplication.

Every mode is out-of-core — data for other partitions is never read, so writes stay cheap even
as the store grows.

## Read it back with pruning

{meth}`~exporgo.datastore.Store.scan` returns a lazy {class}`polars.LazyFrame`. Filter on the
partition keys *before* you collect, and the scan skips whole files:

```python
print(
    store.scan()
    .filter(pl.col("Subject") == "m01")
    .sort("Session", "trial")
    .collect()
)
```

```text
shape: (3, 4)
┌─────────┬─────────┬───────┬──────┐
│ Subject ┆ Session ┆ trial ┆ rt   │
│ ---     ┆ ---     ┆ ---   ┆ ---  │
│ str     ┆ i64     ┆ i64   ┆ f64  │
╞═════════╪═════════╪═══════╪══════╡
│ m01     ┆ 1       ┆ 1     ┆ 0.51 │
│ m01     ┆ 1       ┆ 2     ┆ 0.42 │
│ m01     ┆ 2       ┆ 1     ┆ 0.39 │
└─────────┴─────────┴───────┴──────┘
```

Collecting first and filtering after materializes the whole dataset, defeating the pruning — so
keep the `.filter(...)` on the lazy frame.

## Check what a store contains

The store's **manifest** answers "what's in here?" without scanning the data (which partitions,
and how many rows):

```python
print(store.manifest().partitions())
print(store.manifest().row_count())
```

```text
[{'Subject': 'm01', 'Session': '1'}, {'Subject': 'm01', 'Session': '2'}]
3
```

At the study level, {meth}`study.identities(store="behavior") <exporgo.study.Study.identities>`
returns those partitions as typed identities, and {meth}`~exporgo.study.Study.coverage` folds
them into the full present/missing/unregistered report.
