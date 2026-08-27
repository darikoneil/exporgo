"""Tests for Store: schema-enforced partitioned writes and pruning scans."""

from pathlib import Path

import polars as pl
import pytest

from exporgo.datastore.spec import StoreSpec
from exporgo.datastore.store import Store

BEHAVIOR = {
    "Subject": pl.String,
    "Session": pl.Int64,
    "trial": pl.Int64,
    "lick_rate": pl.Float64,
}


def _spec() -> StoreSpec:
    return StoreSpec(
        name="behavior",
        columns=BEHAVIOR,
        partition_keys=["Subject", "Session"],
        sort_column="trial",
    )


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "Subject": ["m01", "m01", "m02", "m02"],
            "Session": [1, 1, 2, 2],
            "trial": [2, 1, 1, 2],
            "lick_rate": [0.5, 0.6, 0.1, 0.2],
        }
    )


def test_write_creates_hive_partition_layout(tmp_path: Path) -> None:
    Store(tmp_path, _spec()).write(_frame())

    assert (tmp_path / "Subject=m01" / "Session=1").is_dir()
    assert (tmp_path / "Subject=m02" / "Session=2").is_dir()


def test_scan_round_trips_rows_and_columns(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    store.write(_frame())

    out = store.scan().collect()

    assert out.height == 4
    assert set(out.columns) == set(BEHAVIOR)  # partition columns reconstructed
    assert out.schema["Session"] == pl.Int64


def test_scan_filter_on_partition_key(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    store.write(_frame())

    out = store.scan().filter(pl.col("Subject") == "m01").collect()

    assert out.height == 2
    assert set(out["Subject"].to_list()) == {"m01"}


def test_write_rejects_missing_column(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    frame = pl.DataFrame({"Subject": ["m01"], "Session": [1], "trial": [1]})

    with pytest.raises(ValueError, match="lick_rate"):
        store.write(frame)


def test_write_rejects_extra_column(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    frame = _frame().with_columns(pl.lit(1).alias("extra"))

    with pytest.raises(ValueError, match="extra"):
        store.write(frame)


def test_write_appends_without_clobbering(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    store.write(
        pl.DataFrame(
            {"Subject": ["m01"], "Session": [1], "trial": [1], "lick_rate": [0.5]}
        )
    )
    store.write(  # same partition (m01/1) -- must append, not overwrite
        pl.DataFrame(
            {"Subject": ["m01"], "Session": [1], "trial": [2], "lick_rate": [0.6]}
        )
    )

    out = (
        store.scan()
        .filter((pl.col("Subject") == "m01") & (pl.col("Session") == 1))
        .collect()
    )

    assert out.height == 2
    assert set(out["trial"].to_list()) == {1, 2}


def test_write_and_scan_a_list_column_at_full_dtype_fidelity(tmp_path: Path) -> None:
    spec = StoreSpec(
        name="neural",
        columns={"Subject": pl.String, "unit": pl.UInt16, "activity": pl.List(pl.Float64)},
        partition_keys=["Subject"],
    )
    store = Store(tmp_path, spec)
    frame = pl.DataFrame(
        {"Subject": ["m01", "m01"], "unit": [0, 1], "activity": [[0.1, 0.2], [0.3, 0.4]]},
        schema={"Subject": pl.String, "unit": pl.UInt16, "activity": pl.List(pl.Float64)},
    )

    store.write(frame)
    out = store.scan().filter(pl.col("Subject") == "m01").collect()

    assert out.height == 2
    assert out.schema["activity"] == pl.List(pl.Float64)  # array column round-trips
    assert out.schema["unit"] == pl.UInt16  # width preserved, not widened to Int64
    assert out.filter(pl.col("unit") == 0)["activity"].to_list() == [[0.1, 0.2]]


def test_write_casts_to_declared_dtypes(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    frame = _frame().with_columns(pl.col("Session").cast(pl.String))  # wrong dtype in

    store.write(frame)

    assert store.scan().collect().schema["Session"] == pl.Int64


def test_write_logs_a_summary(tmp_path: Path) -> None:
    from loguru import logger

    records: list[str] = []
    logger.enable("exporgo")
    sink_id = logger.add(records.append, level="INFO", format="{message}")
    try:
        Store(tmp_path, _spec()).write(_frame())  # 4 rows across 2 partitions
    finally:
        logger.remove(sink_id)

    joined = " ".join(records).lower()
    assert "behavior" in joined
    assert "4 rows" in joined


def test_schema_property_returns_the_declared_schema(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())  # nothing written yet -> no IO, still works

    assert store.schema == store.spec.polars_schema()
    assert store.schema["Subject"] == pl.String
    assert store.schema["Session"] == pl.Int64


def test_unique_rejects_rewriting_an_existing_identity(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    store.write(_frame())  # partitions m01/1 and m02/2

    with pytest.raises(ValueError, match="already contains"):
        store.write(_frame(), mode="unique")

    assert store.manifest().row_count() == 4  # store unchanged


def test_unique_allows_a_genuinely_new_identity(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    first = pl.DataFrame(
        {"Subject": ["m01"], "Session": [1], "trial": [1], "lick_rate": [0.5]}
    )
    second = pl.DataFrame(
        {"Subject": ["m03"], "Session": [3], "trial": [1], "lick_rate": [0.9]}
    )

    store.write(first, mode="unique")
    store.write(second, mode="unique")

    assert len(store.manifest().partitions()) == 2


def test_unique_is_all_or_nothing(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    store.write(
        pl.DataFrame(
            {"Subject": ["m01"], "Session": [1], "trial": [1], "lick_rate": [0.5]}
        )
    )
    mixed = pl.DataFrame(  # m01/1 already present, m02/2 is new
        {
            "Subject": ["m01", "m02"],
            "Session": [1, 2],
            "trial": [1, 1],
            "lick_rate": [0.5, 0.1],
        }
    )

    with pytest.raises(ValueError, match="already contains"):
        store.write(mixed, mode="unique")

    parts = {(p["Subject"], p["Session"]) for p in store.manifest().partitions()}
    assert ("m01", "1") in parts
    assert ("m02", "2") not in parts  # nothing from the rejected write landed
