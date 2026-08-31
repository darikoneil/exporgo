"""Tests for ArrayStore: per-identity .npy arrays paired with a coordinate catalog."""

from pathlib import Path

import numpy as np
import polars as pl
import pytest
import xarray as xr

from exporgo.datastore.arrays import ArrayStore, ArrayStoreSpec


def _spec(**overrides: object) -> ArrayStoreSpec:
    base: dict[str, object] = {
        "name": "neural",
        "dims": {"unit": pl.Int64, "time": pl.Float64},
        "dtype": np.float32,
        "partition_keys": ("Subject", "Session"),
        "partition_dtypes": {"Subject": pl.String, "Session": pl.Int64},
    }
    base.update(overrides)
    return ArrayStoreSpec(**base)


def _write_one(store: ArrayStore, subject: str = "m01", session: int = 1) -> np.ndarray:
    array = np.arange(4 * 6, dtype=np.float32).reshape(4, 6)
    store.write(
        array,
        coords={"unit": np.arange(4), "time": np.linspace(0.0, 0.5, 6)},
        Subject=subject,
        Session=session,
    )
    return array


def test_spec_rejects_no_dimensions() -> None:
    with pytest.raises(ValueError, match="at least one dimension"):
        _spec(dims={})


def test_spec_rejects_a_partition_key_that_is_also_a_dimension() -> None:
    with pytest.raises(ValueError, match="must not also be dimensions"):
        _spec(dims={"Subject": pl.Int64, "time": pl.Float64})


def test_spec_rejects_a_nested_coordinate_dtype() -> None:
    with pytest.raises(ValueError, match="scalar"):
        _spec(dims={"unit": pl.List(pl.Int64), "time": pl.Float64})


def test_coord_spec_builds_list_columns_over_the_partition_keys() -> None:
    coord_spec = _spec().coord_spec()

    assert coord_spec.partition_keys == ("Subject", "Session")
    assert coord_spec.columns["Subject"] == pl.String
    assert coord_spec.columns["unit"] == pl.List(pl.Int64)
    assert coord_spec.columns["time"] == pl.List(pl.Float64)


def test_write_and_load_round_trips_a_dataarray(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())
    array = _write_one(store)

    loaded = store.load(Subject="m01", Session=1)

    assert isinstance(loaded, xr.DataArray)
    assert loaded.dims == ("unit", "time")
    assert loaded.shape == (4, 6)
    assert loaded.name == "neural"
    np.testing.assert_array_equal(loaded.to_numpy(), array)
    np.testing.assert_array_equal(loaded.coords["unit"].to_numpy(), np.arange(4))
    np.testing.assert_allclose(
        loaded.coords["time"].to_numpy(), np.linspace(0.0, 0.5, 6)
    )


def test_write_casts_to_the_declared_element_dtype(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())
    store.write(
        np.ones((2, 3), dtype=np.float64),  # float64 in -> cast to float32
        coords={"unit": np.arange(2), "time": np.arange(3.0)},
        Subject="m01",
        Session=1,
    )

    assert store.load(Subject="m01", Session=1).dtype == np.float32


def test_load_raises_for_a_missing_identity(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())
    _write_one(store)

    with pytest.raises(KeyError, match="no array for identity"):
        store.load(Subject="m99", Session=9)


def test_write_rejects_the_wrong_rank(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())

    with pytest.raises(ValueError, match="2-D array"):
        store.write(
            np.arange(6, dtype=np.float32),  # 1-D, but two dims declared
            coords={"unit": np.arange(6), "time": np.arange(6.0)},
            Subject="m01",
            Session=1,
        )


def test_write_rejects_a_missing_coordinate(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())

    with pytest.raises(ValueError, match="requires coordinates"):
        store.write(
            np.zeros((2, 3), dtype=np.float32),
            coords={"unit": np.arange(2)},  # 'time' omitted
            Subject="m01",
            Session=1,
        )


def test_write_rejects_an_unknown_coordinate(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())

    with pytest.raises(ValueError, match="Unexpected coordinates"):
        store.write(
            np.zeros((2, 3), dtype=np.float32),
            coords={"unit": np.arange(2), "time": np.arange(3.0), "extra": [1]},
            Subject="m01",
            Session=1,
        )


def test_write_rejects_a_mismatched_coordinate_length(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())

    with pytest.raises(ValueError, match="expected 3 to match axis 1"):
        store.write(
            np.zeros((2, 3), dtype=np.float32),
            coords={"unit": np.arange(2), "time": np.arange(5.0)},  # len 5 != 3
            Subject="m01",
            Session=1,
        )


def test_write_rejects_wrong_identity_keys(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())

    with pytest.raises(ValueError, match="Missing identity keys"):
        store.write(
            np.zeros((2, 3), dtype=np.float32),
            coords={"unit": np.arange(2), "time": np.arange(3.0)},
            Subject="m01",  # 'Session' omitted
        )


def test_unique_refuses_an_existing_identity(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())
    _write_one(store)

    with pytest.raises(ValueError, match="already contains identity"):
        _write_one(store)  # same identity, default mode='unique'

    assert len(store.manifest().partitions()) == 1


def test_overwrite_replaces_the_array_and_its_coordinates(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())
    _write_one(store)

    store.write(
        np.zeros((2, 2), dtype=np.float32),
        coords={"unit": np.array([7, 8]), "time": np.array([0.0, 1.0])},
        mode="overwrite",
        Subject="m01",
        Session=1,
    )

    loaded = store.load(Subject="m01", Session=1)
    assert loaded.shape == (2, 2)
    np.testing.assert_array_equal(loaded.coords["unit"].to_numpy(), [7, 8])
    assert len(store.manifest().fragments) == 1  # prior blob tombstoned
    npys = list(tmp_path.glob("Subject=m01/Session=1/data-*.npy"))
    assert len(npys) == 1  # the tombstoned .npy was deleted


def test_two_identities_coexist(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())
    _write_one(store, "m01", 1)
    _write_one(store, "m02", 2)

    assert store.load(Subject="m01", Session=1).shape == (4, 6)
    assert store.load(Subject="m02", Session=2).shape == (4, 6)
    assert len(store.manifest().partitions()) == 2


def test_a_positional_dimension_has_no_coordinate(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec(dims={"unit": None, "time": pl.Float64}))
    store.write(
        np.zeros((3, 4), dtype=np.float32),
        coords={"time": np.arange(4.0)},  # only 'time' is labelled
        Subject="m01",
        Session=1,
    )

    loaded = store.load(Subject="m01", Session=1)
    assert "time" in loaded.coords
    assert "unit" not in loaded.coords
    np.testing.assert_allclose(loaded.coords["time"].to_numpy(), np.arange(4.0))


def test_scan_coords_exposes_the_catalog(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())
    _write_one(store, "m01", 1)
    _write_one(store, "m02", 2)

    catalog = store.scan_coords().collect()

    assert set(catalog.columns) == {"Subject", "Session", "unit", "time"}
    assert catalog.height == 2
    assert catalog.schema["time"] == pl.List(pl.Float64)


def test_path_reflects_presence(tmp_path: Path) -> None:
    store = ArrayStore(tmp_path, _spec())
    assert store.path(Subject="m01", Session=1) is None

    _write_one(store)
    path = store.path(Subject="m01", Session=1)

    assert path is not None
    assert path.suffix == ".npy"
    assert path.exists()


def test_write_logs_a_summary(tmp_path: Path) -> None:
    from loguru import logger

    records: list[str] = []
    logger.enable("exporgo")
    sink_id = logger.add(records.append, level="INFO", format="{message}")
    try:
        _write_one(store=ArrayStore(tmp_path, _spec()))
    finally:
        logger.remove(sink_id)

    joined = " ".join(records).lower()
    assert "neural" in joined
    assert "array" in joined
