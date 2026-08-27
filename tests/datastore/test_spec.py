"""Tests for StoreSpec: real polars dtypes (no lossy whitelist), scalar-key guard."""

import polars as pl
import pytest
from pydantic import ValidationError

from exporgo.datastore.spec import StoreSpec

BEHAVIOR = {
    "Subject": pl.String,
    "Session": pl.Int64,
    "trial": pl.Int64,
    "lick_rate": pl.Float64,
}


def test_defaults_the_max_rows_write_settings() -> None:
    spec = StoreSpec(name="s", columns={"Subject": pl.String}, partition_keys=("Subject",))

    assert spec.max_rows_per_file == 25_000_000
    assert spec.max_rows_per_group is None


def test_rejects_a_negative_max_rows_setting() -> None:
    with pytest.raises(ValidationError):
        StoreSpec(
            name="s",
            columns={"Subject": pl.String},
            partition_keys=("Subject",),
            max_rows_per_file=-1,
        )


def test_polars_schema_preserves_declared_dtypes_exactly() -> None:
    spec = StoreSpec(
        name="neural",
        columns={"Subject": pl.String, "unit": pl.UInt16, "activity": pl.List(pl.Float32)},
        partition_keys=["Subject"],
    )
    schema = spec.polars_schema()
    assert schema["unit"] == pl.UInt16  # not widened to Int64
    assert schema["activity"] == pl.List(pl.Float32)  # list + Float32 preserved
    assert schema["Subject"] == pl.String


def test_exposes_column_names_and_partition_keys() -> None:
    spec = StoreSpec(name="b", columns=BEHAVIOR, partition_keys=["Subject", "Session"])
    assert set(spec.column_names) == set(BEHAVIOR)
    assert spec.partition_keys == ("Subject", "Session")


def test_rejects_partition_key_absent_from_columns() -> None:
    with pytest.raises(ValidationError):
        StoreSpec(name="b", columns=BEHAVIOR, partition_keys=["Group"])


def test_rejects_more_than_three_partition_keys() -> None:
    columns = {"a": pl.String, "b": pl.String, "c": pl.String, "d": pl.String}
    with pytest.raises(ValidationError):
        StoreSpec(name="b", columns=columns, partition_keys=["a", "b", "c", "d"])


def test_requires_at_least_one_partition_key() -> None:
    with pytest.raises(ValidationError):
        StoreSpec(name="b", columns=BEHAVIOR, partition_keys=[])


def test_rejects_duplicate_partition_keys() -> None:
    with pytest.raises(ValidationError):
        StoreSpec(name="b", columns=BEHAVIOR, partition_keys=["Subject", "Subject"])


def test_rejects_empty_columns() -> None:
    with pytest.raises(ValidationError):
        StoreSpec(name="b", columns={}, partition_keys=["Subject"])


def test_rejects_sort_column_absent_from_columns() -> None:
    with pytest.raises(ValidationError):
        StoreSpec(
            name="b", columns=BEHAVIOR, partition_keys=["Subject"], sort_column="nope"
        )


def test_rejects_nested_dtype_as_partition_key() -> None:
    with pytest.raises(ValidationError):
        StoreSpec(
            name="b",
            columns={"Subject": pl.String, "activity": pl.List(pl.Float64)},
            partition_keys=["activity"],
        )


def test_rejects_nested_dtype_as_sort_column() -> None:
    with pytest.raises(ValidationError):
        StoreSpec(
            name="b",
            columns={"Subject": pl.String, "activity": pl.List(pl.Float64)},
            partition_keys=["Subject"],
            sort_column="activity",
        )
