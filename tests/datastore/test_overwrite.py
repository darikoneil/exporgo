"""Tests for overwrite-by-key: replacing a partition instead of appending."""

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


def _row(subject: str, session: int, trial: int, lick: float) -> pl.DataFrame:
    return pl.DataFrame(
        {"Subject": [subject], "Session": [session], "trial": [trial], "lick_rate": [lick]}
    )


def test_append_is_the_default(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    store.write(_row("m01", 1, 1, 0.5))
    store.write(_row("m01", 1, 2, 0.6))  # default -> append
    assert store.scan().collect().height == 2


def test_overwrite_replaces_only_the_written_partition(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    store.write(
        pl.DataFrame(
            {
                "Subject": ["m01", "m02"],
                "Session": [1, 2],
                "trial": [1, 1],
                "lick_rate": [0.5, 0.1],
            }
        )
    )

    store.write(_row("m01", 1, 9, 0.9), mode="overwrite")  # replace m01/1 only

    out = store.scan().collect()
    m01 = out.filter(pl.col("Subject") == "m01")
    m02 = out.filter(pl.col("Subject") == "m02")
    assert m01["trial"].to_list() == [9]  # m01/1 replaced
    assert m01["lick_rate"].to_list() == [0.9]
    assert m02.height == 1  # m02/2 untouched
    assert m02["lick_rate"].to_list() == [0.1]


def test_overwrite_prunes_old_fragments_from_manifest(tmp_path: Path) -> None:
    store = Store(tmp_path, _spec())
    store.write(_row("m01", 1, 1, 0.5))
    store.write(_row("m01", 1, 2, 0.6))  # append -> 2 fragments in m01/1
    assert len(store.manifest().fragments) == 2

    store.write(_row("m01", 1, 9, 0.9), mode="overwrite")

    manifest = store.manifest()
    assert len(manifest.fragments) == 1  # old two removed, one new
    assert manifest.row_count() == 1
