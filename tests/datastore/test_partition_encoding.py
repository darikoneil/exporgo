"""Regression tests: percent-encoded and boolean Hive partition values.

pyarrow percent-encodes Hive partition values on write (``Subject=m 01#a`` lands in the
directory ``Subject=m%2001%23a``) and renders booleans lowercase (``Flag=false``). These
tests pin the invariant that manifests hold *raw* values, so ``mode="unique"`` refusal,
``mode="overwrite"`` replacement, ``identities()``, and the array store's blob/coords
paths all agree for values containing spaces, ``#``, ``%``, and ``=``.
"""

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from exporgo.datastore.arrays import ArrayStore, ArrayStoreSpec
from exporgo.datastore.spec import StoreSpec
from exporgo.datastore.store import Store
from exporgo.experiment.experiment import Experiment

SPECIAL = "m 01#a"  # space, '#' -- pyarrow writes the dir 'Subject=m%2001%23a'
NASTY = "b%=c"  # '%' and '=' both percent-encode


def _store_spec() -> StoreSpec:
    return StoreSpec(
        name="behavior",
        columns={"Subject": pl.String, "value": pl.Int64},
        partition_keys=["Subject"],
    )


def _frame(subject: str, value: int) -> pl.DataFrame:
    return pl.DataFrame({"Subject": [subject], "value": [value]})


def _array_spec() -> ArrayStoreSpec:
    return ArrayStoreSpec(
        name="neural",
        dims={"time": pl.Float64},
        dtype=np.float32,
        partition_keys=("Subject",),
        partition_dtypes={"Subject": pl.String},
    )


@pytest.mark.parametrize("subject", [SPECIAL, NASTY])
def test_manifest_records_raw_partition_values(tmp_path: Path, subject: str) -> None:
    store = Store(tmp_path, _store_spec())
    store.write(_frame(subject, 1))

    partitions = store.manifest().partitions()

    assert partitions == [{"Subject": subject}]


@pytest.mark.parametrize("subject", [SPECIAL, NASTY])
def test_unique_mode_refuses_duplicate_special_value(
    tmp_path: Path, subject: str
) -> None:
    store = Store(tmp_path, _store_spec())
    store.write(_frame(subject, 1), mode="unique")

    with pytest.raises(ValueError, match="already contains"):
        store.write(_frame(subject, 2), mode="unique")


@pytest.mark.parametrize("subject", [SPECIAL, NASTY])
def test_overwrite_replaces_special_value_partition(
    tmp_path: Path, subject: str
) -> None:
    store = Store(tmp_path, _store_spec())
    store.write(_frame(subject, 1))
    store.write(_frame(subject, 2), mode="overwrite")

    out = store.scan().collect()

    assert out.height == 1  # the old fragment was actually removed
    assert out["Subject"].to_list() == [subject]
    assert out["value"].to_list() == [2]


def test_experiment_identities_returns_raw_store_values(tmp_path: Path) -> None:
    experiment = Experiment(name="s", root=tmp_path, identity=["Subject"])
    store = experiment.declare_store(
        "behavior", {"Subject": pl.String, "value": pl.Int64}
    )
    store.write(_frame(SPECIAL, 1))

    identities = experiment.identities(store="behavior")

    assert {identity["Subject"] for identity in identities} == {SPECIAL}


@pytest.mark.parametrize("subject", [SPECIAL, NASTY])
def test_array_store_round_trips_special_value(tmp_path: Path, subject: str) -> None:
    store = ArrayStore(tmp_path, _array_spec())
    array = np.arange(5, dtype=np.float32)
    time = np.linspace(0.0, 0.4, 5)
    store.write(array, coords={"time": time}, Subject=subject)

    loaded = store.load(Subject=subject)

    np.testing.assert_array_equal(loaded.to_numpy(), array)
    # The coords land in the pyarrow-encoded directory; _read_coords must find them.
    np.testing.assert_array_equal(loaded.coords["time"].to_numpy(), time)


def test_array_store_unique_refuses_duplicate_special_value(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _array_spec())
    store.write(
        np.arange(3, dtype=np.float32),
        coords={"time": np.arange(3.0)},
        Subject=SPECIAL,
    )

    with pytest.raises(ValueError, match="already contains"):
        store.write(
            np.arange(3, dtype=np.float32),
            coords={"time": np.arange(3.0)},
            Subject=SPECIAL,
        )


def test_array_store_overwrite_replaces_special_value(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _array_spec())
    store.write(
        np.zeros(3, dtype=np.float32),
        coords={"time": np.arange(3.0)},
        Subject=SPECIAL,
    )
    replacement = np.ones(3, dtype=np.float32)
    store.write(
        replacement,
        coords={"time": np.arange(3.0)},
        mode="overwrite",
        Subject=SPECIAL,
    )

    loaded = store.load(Subject=SPECIAL)

    np.testing.assert_array_equal(loaded.to_numpy(), replacement)
    npy_files = [
        path for path in tmp_path.rglob("data-*.npy") if path.suffix == ".npy"
    ]
    assert len(npy_files) == 1  # the old blob was actually deleted


def test_bool_partition_round_trips_through_store_identities(tmp_path: Path) -> None:
    from exporgo.experiment.identity import IdentityKey

    experiment = Experiment(
        name="s", root=tmp_path, identity=[IdentityKey(name="Flag", dtype="bool")]
    )
    store = experiment.declare_store("events", {"Flag": pl.Boolean, "value": pl.Int64})
    store.write(pl.DataFrame({"Flag": [False], "value": [1]}))

    identities = experiment.identities(store="events")

    assert len(identities) == 1
    flag = next(iter(identities))["Flag"]
    assert flag is False


def test_bool_partition_unique_mode_refuses_duplicate(tmp_path: Path) -> None:
    spec = StoreSpec(
        name="events",
        columns={"Flag": pl.Boolean, "value": pl.Int64},
        partition_keys=["Flag"],
    )
    store = Store(tmp_path, spec)
    store.write(pl.DataFrame({"Flag": [False], "value": [1]}), mode="unique")

    with pytest.raises(ValueError, match="already contains"):
        store.write(pl.DataFrame({"Flag": [False], "value": [2]}), mode="unique")
