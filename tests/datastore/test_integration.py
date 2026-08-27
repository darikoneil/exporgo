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


def test_stores_property_exposes_declared_specs(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject", "Session"])
    spec = study.declare_store("behavior", BEHAVIOR)

    stores = study.stores
    assert stores["behavior"] is spec

    stores.clear()  # returned mapping is a copy; mutating it must not affect the study
    assert "behavior" in study.stores


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


def test_identities_of_a_store_returns_typed_identities(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject", "Session"])
    study.declare_store("behavior", BEHAVIOR, sort_column="trial")
    study.store("behavior").write(
        pl.DataFrame(
            {
                "Subject": ["m01", "m02"],
                "Session": [1, 2],
                "trial": [1, 1],
                "lick_rate": [0.5, 0.1],
            }
        )
    )

    assert study.identities(store="behavior") == {
        study.identity.identity(Subject="m01", Session=1),
        study.identity.identity(Subject="m02", Session=2),
    }


def test_identities_of_a_resource_returns_registered_present(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_resource("beh", "{Subject}/behavior.csv")
    study.register(Subject="m01")
    study.register(Subject="m02")
    (tmp_path / "m01").mkdir()
    (tmp_path / "m01" / "behavior.csv").write_text("x", encoding="utf-8")

    assert study.identities(resource="beh") == {study.identity.identity(Subject="m01")}


def test_identities_requires_exactly_one_target(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path)
    with pytest.raises(ValueError, match="one of"):
        study.identities()
    with pytest.raises(ValueError, match="only one"):
        study.identities(store="a", resource="b")


def test_identities_unknown_name_raises(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path)
    with pytest.raises(KeyError):
        study.identities(store="nope")
    with pytest.raises(KeyError):
        study.identities(resource="nope")


def test_coverage_reports_present_missing_and_unregistered(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_store(
        "behavior", {"Subject": pl.String, "trial": pl.Int64}, sort_column="trial"
    )
    study.register(Subject="m01")  # registered + written -> present
    study.register(Subject="m02")  # registered, never written -> missing
    study.store("behavior").write(  # m03 written but not registered -> unregistered
        pl.DataFrame({"Subject": ["m01", "m03"], "trial": [1, 1]})
    )

    report = study.coverage()
    m01 = study.identity.identity(Subject="m01")
    m02 = study.identity.identity(Subject="m02")
    m03 = study.identity.identity(Subject="m03")

    assert (m01, "behavior") in report.present
    assert (m02, "behavior") in report.missing
    assert (m03, "behavior") in report.unregistered
    assert not report.is_complete
    assert report.identities("behavior") == {m01}
