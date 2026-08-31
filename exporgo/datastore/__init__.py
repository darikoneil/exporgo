"""Datastore layer -- fast, polars/Parquet component stores for a study's bulk data.

A study is a catalog of named component stores (behavior, neural, ...), each keyed by the
study's identity vocabulary. There are two store kinds. A tabular
:class:`~exporgo.datastore.store.Store` is an independent Hive-partitioned Parquet dataset with
a strict, declared schema, retrieved via lazy, partition-pruned polars queries. An
:class:`~exporgo.datastore.arrays.ArrayStore` holds one dense N-D array per identity as a NumPy
``.npy`` blob paired with a coordinate catalog, loaded as an :class:`xarray.DataArray`. See
:class:`~exporgo.datastore.spec.StoreSpec` and
:class:`~exporgo.datastore.arrays.ArrayStoreSpec`.
"""

from exporgo.datastore.arrays import ArrayStore, ArrayStoreSpec
from exporgo.datastore.manifest import FragmentEntry, Manifest
from exporgo.datastore.spec import StoreSpec
from exporgo.datastore.store import Store

__all__ = [
    "ArrayStore",
    "ArrayStoreSpec",
    "FragmentEntry",
    "Manifest",
    "Store",
    "StoreSpec",
]
