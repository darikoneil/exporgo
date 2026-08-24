"""Datastore layer -- fast, polars/Parquet component stores for a study's bulk data.

A study is a catalog of named component stores (behavior, neural, ...), each an
independent Hive-partitioned Parquet dataset with a strict, declared schema. Data is
dumped in and retrieved via lazy, partition-pruned polars queries, keyed by the study's
identity vocabulary. See :class:`~exporgo.datastore.spec.StoreSpec` and
:class:`~exporgo.datastore.store.Store`.
"""

from exporgo.datastore.manifest import FragmentEntry, Manifest
from exporgo.datastore.spec import StoreSpec
from exporgo.datastore.store import Store

__all__ = ["FragmentEntry", "Manifest", "Store", "StoreSpec"]
