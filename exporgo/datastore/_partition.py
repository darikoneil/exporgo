"""Hive partition-path helpers shared by the tabular and array stores.

Both store kinds address data by the same Hive ``key=value/...`` partition layout, keyed on
the study's identity vocabulary. These free functions are the single, consistently-named
vocabulary for rendering an identity to that layout and for reading partitions back out of a
manifest, so :mod:`exporgo.datastore.store` and :mod:`exporgo.datastore.arrays` need not each
carry their own (divergently named) copy.

Every function takes ``partition_keys`` explicitly and stringifies values the way the Hive
path encodes them, so an identity, the directory it lands in, and a manifest partition all
compare as the same value tuple.
"""

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

__all__ = [
    "dict_of_identity",
    "existing",
    "from_path",
    "subpath",
    "tuple_of_identity",
    "tuple_of_partition",
]


def subpath(partition_keys: Sequence[str], identity: Mapping[str, Any]) -> str:
    """Render an identity as its Hive partition sub-path (``key=value/...``)."""
    return "/".join(f"{key}={identity[key]}" for key in partition_keys)


def dict_of_identity(
    partition_keys: Sequence[str], identity: Mapping[str, Any]
) -> dict[str, str]:
    """Render an identity as a stringified Hive ``{key: value}`` mapping."""
    return {key: str(identity[key]) for key in partition_keys}


def tuple_of_identity(
    partition_keys: Sequence[str], identity: Mapping[str, Any]
) -> tuple[str, ...]:
    """Render an identity as its stringified partition-value tuple, in key order."""
    return tuple(str(identity[key]) for key in partition_keys)


def tuple_of_partition(
    partition_keys: Sequence[str], partition: Mapping[str, str]
) -> tuple[str, ...]:
    """Order a manifest partition dict into a value tuple by ``partition_keys``."""
    return tuple(partition.get(key, "") for key in partition_keys)


def from_path(relative: Path) -> dict[str, str]:
    """Parse Hive ``key=value`` segments from a fragment's relative path."""
    partition: dict[str, str] = {}
    for segment in relative.parts[:-1]:
        key, separator, value = segment.partition("=")
        if separator:
            partition[key] = value
    return partition


def existing(
    partition_keys: Sequence[str], partitions: Iterable[Mapping[str, str]]
) -> set[tuple[str, ...]]:
    """The set of partition-value tuples present, from a manifest's partitions."""
    return {tuple_of_partition(partition_keys, partition) for partition in partitions}
