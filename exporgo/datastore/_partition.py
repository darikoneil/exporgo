"""Hive partition-path helpers shared by the tabular and array stores.

Both store kinds address data by the same Hive ``key=value/...`` partition layout, keyed on
the experiment's identity vocabulary. These free functions are the single, consistently-named
vocabulary for rendering an identity to that layout and for reading partitions back out of a
manifest, so :mod:`exporgo.datastore.store` and :mod:`exporgo.datastore.arrays` need not each
carry their own (divergently named) copy.

Two representations exist, and each function is explicit about which one it speaks:

- **Raw**: the partition value as the user wrote it (``"m 01#a"``), stringified the way
  pyarrow renders it *before* escaping (notably, booleans lowercase: ``"true"``/``"false"``).
  Manifests always hold raw values, so an identity and a manifest partition compare equal.
- **Encoded**: the percent-encoded form pyarrow's Hive writer puts in directory names
  (``"m%2001%23a"``). Only path construction (:func:`subpath`) and path parsing
  (:func:`from_path`, which decodes back to raw) touch this form.

pyarrow escapes partition path segments exactly like :func:`urllib.parse.quote` with
``safe=""`` (verified empirically against pyarrow's Hive writer), so :func:`subpath` builds
directory names byte-for-byte identical to the ones pyarrow creates.
"""

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

__all__ = [
    "dict_of_identity",
    "existing",
    "from_path",
    "subpath",
    "tuple_of_identity",
    "tuple_of_partition",
]


def _stringify(value: Any) -> str:
    """Render one partition value as its raw Hive string (booleans lowercase)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _encode(text: str) -> str:
    """Percent-encode one path segment exactly as pyarrow's Hive writer does."""
    return quote(text, safe="")


def subpath(partition_keys: Sequence[str], identity: Mapping[str, Any]) -> str:
    """Render an identity as its **encoded** Hive partition sub-path (``key=value/...``).

    The returned segments are percent-encoded the same way pyarrow's Hive writer encodes
    them, so this sub-path names the directories pyarrow actually creates on disk.
    """
    return "/".join(
        f"{_encode(key)}={_encode(_stringify(identity[key]))}" for key in partition_keys
    )


def dict_of_identity(
    partition_keys: Sequence[str], identity: Mapping[str, Any]
) -> dict[str, str]:
    """Render an identity as a **raw** stringified ``{key: value}`` mapping."""
    return {key: _stringify(identity[key]) for key in partition_keys}


def tuple_of_identity(
    partition_keys: Sequence[str], identity: Mapping[str, Any]
) -> tuple[str, ...]:
    """Render an identity as its **raw** stringified value tuple, in key order."""
    return tuple(_stringify(identity[key]) for key in partition_keys)


def tuple_of_partition(
    partition_keys: Sequence[str], partition: Mapping[str, str]
) -> tuple[str, ...]:
    """Order a manifest partition dict into a value tuple by ``partition_keys``."""
    return tuple(partition.get(key, "") for key in partition_keys)


def from_path(relative: Path) -> dict[str, str]:
    """Parse Hive ``key=value`` segments from a fragment's relative path, **decoded to raw**.

    pyarrow percent-encodes partition path segments on write; this decodes them back
    (via :func:`urllib.parse.unquote`), so manifests always record raw values and compare
    equal to the identities users write with.
    """
    partition: dict[str, str] = {}
    for segment in relative.parts[:-1]:
        key, separator, value = segment.partition("=")
        if separator:
            partition[unquote(key)] = unquote(value)
    return partition


def existing(
    partition_keys: Sequence[str], partitions: Iterable[Mapping[str, str]]
) -> set[tuple[str, ...]]:
    """The set of partition-value tuples present, from a manifest's partitions."""
    return {tuple_of_partition(partition_keys, partition) for partition in partitions}
