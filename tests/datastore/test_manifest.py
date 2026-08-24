"""Tests for the per-store manifest (the store's fragment inventory)."""

from pathlib import Path

import polars as pl

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
            "Subject": ["m01", "m02"],
            "Session": [1, 2],
            "trial": [1, 1],
            "lick_rate": [0.5, 0.1],
        }
    )


def test_manifest_is_empty_before_any_write(tmp_path: Path) -> None:
    manifest = Store(tmp_path, _spec()).manifest()
    assert manifest.schema_version == 1
    assert manifest.fragments == []
    assert manifest.row_count() == 0


def test_write_records_one_fragment_per_partition(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    store.write(_frame())

    manifest = store.manifest()
    assert len(manifest.fragments) == 2
    assert manifest.row_count() == 2
    assert {"Subject": "m01", "Session": "1"} in manifest.partitions()
    assert {"Subject": "m02", "Session": "2"} in manifest.partitions()
    assert all(fragment.path.endswith(".parquet") for fragment in manifest.fragments)


def test_manifest_accumulates_across_writes(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    store.write(_frame())
    store.write(
        pl.DataFrame(
            {"Subject": ["m01"], "Session": [1], "trial": [2], "lick_rate": [0.6]}
        )
    )

    manifest = store.manifest()
    assert manifest.row_count() == 3
    m01_session1 = [
        fragment
        for fragment in manifest.fragments
        if fragment.partition == {"Subject": "m01", "Session": "1"}
    ]
    assert len(m01_session1) == 2  # a fragment from each write, not overwritten


def test_scan_still_works_with_manifest_present(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    store.write(_frame())

    out = store.scan().collect()
    assert out.height == 2
    assert set(out.columns) == set(BEHAVIOR)
