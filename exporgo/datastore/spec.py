"""Store specifications: a datastore component's declared schema, keys, sort order."""

from typing import Any, ClassVar, Self

import polars as pl
from pydantic import BaseModel, ConfigDict, model_validator

__all__ = ["StoreSpec"]

_MIN_PARTITION_KEYS = 1
_MAX_PARTITION_KEYS = 3

_NESTED_DTYPES = (pl.List, pl.Array, pl.Struct)
"""polars dtypes that cannot serve as partition or sort keys."""


class StoreSpec(BaseModel):
    """Declares one datastore component: its columns, partition keys, and sort order.

    ``columns`` maps each column name to a **polars dtype** (any polars type, at full
    fidelity -- exact int/float widths, ``List``/``Array``/``Struct``, temporal, etc.).
    The schema is strict and enforced on write. Partition keys (1-3) drive the on-disk
    Hive layout and pruning; the optional sort column enables row-group range pruning.
    Partition and sort keys must be scalar (non-nested) columns.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, arbitrary_types_allowed=True
    )

    name: str
    columns: dict[str, Any]
    partition_keys: tuple[str, ...]
    sort_column: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Enforce non-empty columns, 1-3 unique in-schema scalar keys, valid sort col."""
        if not self.columns:
            msg = "A store must declare at least one column."
            raise ValueError(msg)
        count = len(self.partition_keys)
        if not _MIN_PARTITION_KEYS <= count <= _MAX_PARTITION_KEYS:
            msg = (
                f"A store needs {_MIN_PARTITION_KEYS}-{_MAX_PARTITION_KEYS} partition "
                f"keys, got {count}."
            )
            raise ValueError(msg)
        if len(set(self.partition_keys)) != count:
            msg = f"Partition keys must be unique, got {list(self.partition_keys)}."
            raise ValueError(msg)
        unknown = [key for key in self.partition_keys if key not in self.columns]
        if unknown:
            msg = f"Partition keys not among declared columns: {unknown}."
            raise ValueError(msg)
        if self.sort_column is not None and self.sort_column not in self.columns:
            msg = f"Sort column {self.sort_column!r} is not a declared column."
            raise ValueError(msg)
        self._reject_nested_keys()
        return self

    def _reject_nested_keys(self) -> None:
        """Reject nested (List/Array/Struct) dtypes used as partition or sort keys."""
        schema = self.polars_schema()
        keys = list(self.partition_keys)
        if self.sort_column is not None:
            keys.append(self.sort_column)
        nested = [key for key in keys if isinstance(schema[key], _NESTED_DTYPES)]
        if nested:
            msg = f"Partition/sort keys must be scalar; these are nested: {nested}."
            raise ValueError(msg)

    @property
    def column_names(self) -> tuple[str, ...]:
        """The declared column names, in declaration order."""
        return tuple(self.columns)

    def polars_schema(self) -> pl.Schema:
        """The declared schema as a :class:`polars.Schema` (column -> dtype)."""
        return pl.Schema(self.columns)
