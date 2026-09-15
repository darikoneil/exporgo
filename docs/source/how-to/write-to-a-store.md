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
experiment's identity keys; an optional `sort_column` enables row-group range pruning:

```python
import polars as pl

experiment.declare_store(
    "behavior",
    {"Subject": pl.String, "Session": pl.Int64, "trial": pl.Int64, "rt": pl.Float64},
    sort_column="trial",
)
store = experiment.store("behavior")
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

Every mode is out-of-core: data for other partitions is never read, so writes stay cheap even
as the store grows.

The modes also differ under **concurrent writers**. `append` is multi-writer safe, even into the
same partition: every fragment and manifest entry is uniquely named and the log is append-only.
`unique` and `overwrite` are check-then-act over the manifest, reading, deciding, and then
writing, so two writers aiming at the *same* partition can interleave and both land. Use them
where one writer owns the partition. See
[Storage and concurrency](../explanation/storage-and-concurrency).

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

Collecting first and filtering after materializes the whole dataset, defeating the pruning. Keep
the `.filter(...)` on the lazy frame.

A store you've declared but not yet written to scans as an **empty frame with the declared
schema**, not an error:

```python
store = experiment.declare_store(
    "features", {"Subject": pl.String, "score": pl.Float64}, partition_keys=["Subject"]
)
print(store.scan().collect())
```

```text
shape: (0, 2)
┌─────────┬───────┐
│ Subject ┆ score │
│ ---     ┆ ---   │
│ str     ┆ f64   │
╞═════════╪═══════╡
└─────────┴───────┘
```

The schema is there and the frame is simply empty, so a query that joins, filters, or concatenates
across stores works the same whether or not data has landed yet. You don't need to guard a scan
with an existence check.

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

At the experiment level, {meth}`experiment.identities(store="behavior") <exporgo.experiment.Experiment.identities>`
returns those partitions as typed identities, and {meth}`~exporgo.experiment.Experiment.coverage` folds
them into the full present/missing/unregistered report.
