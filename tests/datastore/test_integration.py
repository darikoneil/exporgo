"""Integration: Study as a catalog of datastores keyed by the identity vocabulary."""

from pathlib import Path

import polars as pl
import pytest

from exporgo.datastore import Store
from exporgo.study import Study

BEHAVIOR = {
    "Subject": pl.String,
    "Session": pl.Int64,
    "trial": pl.Int64,
    "lick_rate": pl.Float64,
}


def test_declare_store_defaults_partition_keys_to_identity(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject", "Session"])
    spec = study.declare_store("behavior", BEHAVIOR)
    assert spec.partition_keys == ("Subject", "Session")


def test_store_returns_a_store_rooted_under_the_study(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject", "Session"])
    study.declare_store("behavior", BEHAVIOR, sort_column="trial")
    store = study.store("behavior")
    assert isinstance(store, Store)
    assert store.root == tmp_path / "behavior"


def test_store_unknown_name_raises(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path)
    with pytest.raises(KeyError):
        study.store("nope")


def test_write_and_scan_through_the_study(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject", "Session"])
    study.declare_store("behavior", BEHAVIOR, sort_column="trial")
    frame = pl.DataFrame(
        {
            "Subject": ["m01", "m02"],
            "Session": [1, 2],
            "trial": [1, 1],
            "lick_rate": [0.5, 0.1],
        }
    )

    study.store("behavior").write(frame)
    out = study.store("behavior").scan().filter(pl.col("Subject") == "m01").collect()

    assert out.height == 1
    assert out["lick_rate"].to_list() == [0.5]


def test_store_catalog_round_trips_through_save_load(tmp_path: Path) -> None:
    study = Study(name="fomo", root=tmp_path, identity=["Subject"])
    study.declare_store(
        "behavior",
        {"Subject": pl.String, "trial": pl.Int64, "lick_rate": pl.Float64},
        sort_column="trial",
    )
    study.save()

    spec = Study.load(tmp_path).store("behavior").spec
    assert spec.partition_keys == ("Subject",)
    assert spec.sort_column == "trial"
    assert spec.polars_schema()["lick_rate"] == pl.Float64
