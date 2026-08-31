# Datastore (`exporgo.datastore`)

The datastore layer: schema-enforced, Hive-partitioned component stores in two kinds. A
{class}`~exporgo.datastore.StoreSpec` declares a tabular store's schema and partition keys and a
{class}`~exporgo.datastore.Store` reads and writes it as polars/Parquet; an
{class}`~exporgo.datastore.ArrayStoreSpec` declares an array store and an
{class}`~exporgo.datastore.ArrayStore` writes one `.npy` array per identity plus a coordinate
catalog, loaded as an {class}`xarray.DataArray`. A {class}`~exporgo.datastore.Manifest` records
what each store contains. This layer ships with the `exporgo[datastore]` extra; every name below
is exported from `exporgo.datastore.__all__`.

## Tabular store

A tabular store is a Hive-partitioned Parquet dataset exporgo owns and writes under a strict,
declared schema. {class}`~exporgo.datastore.StoreSpec` declares the columns, partition keys, and
sort order; {class}`~exporgo.datastore.Store` validates and casts writes, then hands back a lazy,
partition-prunable {class}`polars.LazyFrame`. Reach for one for rows you want to query across
identities — see [Write to a store](../how-to/write-to-a-store).

```python
store = study.store("behavior")
store.write(frame, mode="unique")
store.scan().filter(pl.col("Subject") == "m01").collect()
```

```{eval-rst}
.. autopydantic_model:: exporgo.datastore.StoreSpec
   :members:

.. autoclass:: exporgo.datastore.Store
   :members:
```

## Array store

An array store holds exactly one dense N-D array per identity, stored as a NumPy `.npy` blob and
paired with a coordinate catalog. {class}`~exporgo.datastore.ArrayStoreSpec` declares the ordered
dimensions, the element dtype, and the partition keys; {class}`~exporgo.datastore.ArrayStore`
writes each identity's array and coordinates and reassembles them into an
{class}`xarray.DataArray` on {meth}`~exporgo.datastore.ArrayStore.load`. See
[Store arrays with coordinates](../how-to/store-arrays).

```python
store = study.array_store("neural")
store.write(traces, coords={"unit": units, "time": timestamps}, Subject="m01", Session=1)
neural = store.load(Subject="m01", Session=1)   # an xarray.DataArray
```

```{eval-rst}
.. autopydantic_model:: exporgo.datastore.ArrayStoreSpec
   :members:

.. autoclass:: exporgo.datastore.ArrayStore
   :members:
```

## Manifest

Every store keeps an append-only manifest, the commit log of the fragments written to it, so it
can answer "what's in here?" (which partitions, which files, how many rows) without scanning the
data. A {class}`~exporgo.datastore.Manifest` is the aggregated, tombstone-applied view;
{class}`~exporgo.datastore.FragmentEntry` is one written fragment's record. Reach for these when
you need store membership without reading the Parquet.

```{eval-rst}
.. autoclass:: exporgo.datastore.Manifest
   :members:

.. autoclass:: exporgo.datastore.FragmentEntry
   :members:
```
