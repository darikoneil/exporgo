# Datastore (`exporgo.datastore`)

The datastore layer: schema-enforced, Hive-partitioned component stores in two kinds. A
{class}`~exporgo.datastore.StoreSpec` declares a tabular store's schema and partition keys and a
{class}`~exporgo.datastore.Store` reads and writes it as polars/Parquet; an
{class}`~exporgo.datastore.ArrayStoreSpec` declares an array store and an
{class}`~exporgo.datastore.ArrayStore` writes one `.npy` array per identity plus a coordinate
catalog, loaded as an {class}`xarray.DataArray`. A {class}`~exporgo.datastore.Manifest` records
what each store contains.

```{eval-rst}
.. automodule:: exporgo.datastore
   :members:
   :show-inheritance:
```
