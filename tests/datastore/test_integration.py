"""Integration: Experiment as a catalog of datastores keyed by the identity vocabulary."""

from pathlib import Path

import polars as pl
import pytest

from exporgo.datastore import Store
from exporgo.experiment import Experiment

BEHAVIOR = {
    "Subject": pl.String,
    "Session": pl.Int64,
    "trial": pl.Int64,
    "lick_rate": pl.Float64,
}


def test_declare_store_defaults_partition_keys_to_identity(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject", "Session"])
    store = experiment.declare_store("behavior", BEHAVIOR)
    assert isinstance(store, Store)
    assert store.spec.partition_keys == ("Subject", "Session")


def test_store_returns_a_store_rooted_under_the_experiment(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject", "Session"])
    experiment.declare_store("behavior", BEHAVIOR, sort_column="trial")
    store = experiment.store("behavior")
    assert isinstance(store, Store)
    assert store.root == tmp_path / "behavior"


def test_store_unknown_name_raises(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path)
    with pytest.raises(KeyError):
        experiment.store("nope")


def test_stores_property_exposes_declared_specs(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject", "Session"])
    experiment.declare_store("behavior", BEHAVIOR)

    stores = experiment.stores
    assert stores["behavior"].partition_keys == ("Subject", "Session")

    stores.clear()  # returned mapping is a copy; mutating it must not affect the experiment
    assert "behavior" in experiment.stores


def test_write_and_scan_through_the_experiment(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject", "Session"])
    experiment.declare_store("behavior", BEHAVIOR, sort_column="trial")
    frame = pl.DataFrame(
        {
            "Subject": ["m01", "m02"],
            "Session": [1, 2],
            "trial": [1, 1],
            "lick_rate": [0.5, 0.1],
        }
    )

    experiment.store("behavior").write(frame)
    out = experiment.store("behavior").scan().filter(pl.col("Subject") == "m01").collect()

    assert out.height == 1
    assert out["lick_rate"].to_list() == [0.5]


def test_store_catalog_round_trips_through_save_load(tmp_path: Path) -> None:
    experiment = Experiment(name="fomo", root=tmp_path, identity=["Subject"])
    experiment.declare_store(
        "behavior",
        {"Subject": pl.String, "trial": pl.Int64, "lick_rate": pl.Float64},
        sort_column="trial",
    )
    experiment.save()

    spec = Experiment.load(tmp_path).store("behavior").spec
    assert spec.partition_keys == ("Subject",)
    assert spec.sort_column == "trial"
    assert spec.polars_schema()["lick_rate"] == pl.Float64


def test_identities_of_a_store_returns_typed_identities(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject", "Session"])
    experiment.declare_store("behavior", BEHAVIOR, sort_column="trial")
    experiment.store("behavior").write(
        pl.DataFrame(
            {
                "Subject": ["m01", "m02"],
                "Session": [1, 2],
                "trial": [1, 1],
                "lick_rate": [0.5, 0.1],
            }
        )
    )

    assert experiment.identities(store="behavior") == {
        experiment.identity.identity(Subject="m01", Session=1),
        experiment.identity.identity(Subject="m02", Session=2),
    }


def test_identities_of_a_resource_returns_registered_present(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject"])
    experiment.declare_resource("beh", "{Subject}/behavior.csv")
    experiment.register(Subject="m01")
    experiment.register(Subject="m02")
    (tmp_path / "m01").mkdir()
    (tmp_path / "m01" / "behavior.csv").write_text("x", encoding="utf-8")

    assert experiment.identities(resource="beh") == {experiment.identity.identity(Subject="m01")}


def test_identities_requires_exactly_one_target(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path)
    with pytest.raises(ValueError, match="exactly one"):
        experiment.identities()
    with pytest.raises(ValueError, match="exactly one"):
        experiment.identities(store="a", resource="b")


def test_identities_unknown_name_raises(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path)
    with pytest.raises(KeyError):
        experiment.identities(store="nope")
    with pytest.raises(KeyError):
        experiment.identities(resource="nope")


def test_coverage_reports_present_missing_and_unregistered(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject"])
    experiment.declare_store(
        "behavior", {"Subject": pl.String, "trial": pl.Int64}, sort_column="trial"
    )
    experiment.register(Subject="m01")  # registered + written -> present
    experiment.register(Subject="m02")  # registered, never written -> missing
    experiment.store("behavior").write(  # m03 written but not registered -> unregistered
        pl.DataFrame({"Subject": ["m01", "m03"], "trial": [1, 1]})
    )

    report = experiment.coverage()
    m01 = experiment.identity.identity(Subject="m01")
    m02 = experiment.identity.identity(Subject="m02")
    m03 = experiment.identity.identity(Subject="m03")

    assert (m01, "behavior") in report.present
    assert (m02, "behavior") in report.missing
    assert (m03, "behavior") in report.unregistered
    assert not report.is_complete
    assert report.identities("behavior") == {m01}


def test_sync_registry_registers_store_identities(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject", "Session"])
    experiment.declare_store("behavior", BEHAVIOR, sort_column="trial")
    experiment.store("behavior").write(
        pl.DataFrame(
            {
                "Subject": ["m01", "m02"],
                "Session": [1, 2],
                "trial": [1, 1],
                "lick_rate": [0.5, 0.1],
            }
        )
    )

    newly = experiment.sync_registry()

    expected = {
        experiment.identity.identity(Subject="m01", Session=1),
        experiment.identity.identity(Subject="m02", Session=2),
    }
    assert set(newly) == expected
    assert set(experiment.entities) == expected


def test_validate_ignores_stores(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject"])
    experiment.declare_store("neural", {"Subject": pl.String, "unit": pl.Int64})
    experiment.register(Subject="m01")

    report = experiment.validate()

    assert report.present == ()  # stores are exporgo-owned data, not "indicated" files
    assert report.missing == ()  # store membership is a coverage() concern


def test_coverage_to_polars_null_fills_partial_identities(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject", "Session"])
    experiment.declare_store(
        "neural", {"Subject": pl.String, "Session": pl.Int64, "unit": pl.Int64}
    )
    experiment.declare_store(  # subset partition: Subject only -> partial identities
        "geno", {"Subject": pl.String, "value": pl.String}, partition_keys=["Subject"]
    )
    experiment.register(Subject="m01", Session=1)  # full identity, present in "neural"
    experiment.store("neural").write(
        pl.DataFrame({"Subject": ["m01"], "Session": [1], "unit": [7]})
    )
    experiment.store("geno").write(pl.DataFrame({"Subject": ["m09"], "value": ["wt"]}))

    frame = experiment.coverage().to_polars()

    assert set(frame.columns) == {"Subject", "Session", "component", "status"}
    # m09 is the sole unregistered id: a subset-key (Subject-only) partition of "geno"
    unregistered = frame.filter(pl.col("status") == "unregistered")
    assert unregistered["Subject"].to_list() == ["m09"]
    assert unregistered["Session"].to_list() == [None]  # partial identity -> null-filled
    assert unregistered["component"].to_list() == ["geno"]


def test_store_reads_max_rows_from_its_spec(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject"])
    experiment.declare_store(
        "behavior", {"Subject": pl.String}, max_rows_per_file=7, max_rows_per_group=3
    )

    spec = experiment.store("behavior").spec

    assert spec.max_rows_per_file == 7
    assert spec.max_rows_per_group == 3


def test_max_rows_settings_round_trip_through_save_load(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject"])
    experiment.declare_store(
        "behavior",
        {"Subject": pl.String, "trial": pl.Int64},
        max_rows_per_file=1_000,  # a set value round-trips exactly
        max_rows_per_group=None,  # None (default) stays None
    )
    experiment.save()

    spec = Experiment.load(tmp_path).store("behavior").spec
    assert spec.max_rows_per_file == 1_000
    assert spec.max_rows_per_group is None


def test_max_rows_none_round_trips_via_the_zero_sentinel(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject"])
    experiment.declare_store(
        "behavior",
        {"Subject": pl.String},
        max_rows_per_file=None,  # deliberate "no limit" survives (None -> 0 -> None)
        max_rows_per_group=5_000,
    )
    experiment.save()

    spec = Experiment.load(tmp_path).store("behavior").spec
    assert spec.max_rows_per_file is None
    assert spec.max_rows_per_group == 5_000
