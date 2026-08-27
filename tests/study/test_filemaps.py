"""Tests for FileMap: recorded external file locations per identity."""

from pathlib import Path

import pytest

from exporgo.study import FileMap
from exporgo.study.identity import IdentityKey, IdentitySchema

SCHEMA = IdentitySchema(keys=["Subject", IdentityKey(name="Session", dtype="int")])


def _filemap(tmp_path: Path) -> FileMap:
    return FileMap(tmp_path / "raw", "raw", SCHEMA)


def test_record_defaults_the_name_to_the_stem(tmp_path: Path) -> None:
    fm = _filemap(tmp_path)

    recorded = fm.record("Z:/scope/m01_s1.tif", Subject="m01", Session=1)

    assert recorded == Path("Z:/scope/m01_s1.tif")
    assert fm.path("m01_s1", Subject="m01", Session=1) == Path("Z:/scope/m01_s1.tif")


def test_record_with_explicit_names_and_paths(tmp_path: Path) -> None:
    fm = _filemap(tmp_path)

    fm.record("Z:/a/ch0.tif", Subject="m01", Session=1)  # name -> "ch0"
    fm.record("Z:/a/ch1.tif", name="red", Subject="m01", Session=1)

    assert fm.paths(Subject="m01", Session=1) == {
        "ch0": Path("Z:/a/ch0.tif"),
        "red": Path("Z:/a/ch1.tif"),
    }


def test_paths_empty_for_an_unrecorded_identity(tmp_path: Path) -> None:
    assert _filemap(tmp_path).paths(Subject="m01", Session=1) == {}


def test_path_unknown_name_raises(tmp_path: Path) -> None:
    fm = _filemap(tmp_path)
    fm.record("Z:/a/ch0.tif", Subject="m01", Session=1)

    with pytest.raises(KeyError):
        fm.path("nope", Subject="m01", Session=1)


def test_exists_reflects_the_filesystem(tmp_path: Path) -> None:
    fm = _filemap(tmp_path)
    real = tmp_path / "data.tif"
    fm.record(real, Subject="m01", Session=1)

    assert fm.exists(Subject="m01", Session=1) is False  # recorded, not yet on disk
    real.write_text("x", encoding="utf-8")
    assert fm.exists(Subject="m01", Session=1) is True


def test_identities_lists_recorded_identities(tmp_path: Path) -> None:
    fm = _filemap(tmp_path)
    fm.record("Z:/a.tif", Subject="m01", Session=1)
    fm.record("Z:/b.tif", Subject="m02", Session=2)

    assert fm.identities() == {
        SCHEMA.identity(Subject="m01", Session=1),
        SCHEMA.identity(Subject="m02", Session=2),
    }


def test_records_persist_across_instances(tmp_path: Path) -> None:
    _filemap(tmp_path).record("Z:/a.tif", Subject="m01", Session=1)

    reopened = FileMap(tmp_path / "raw", "raw", SCHEMA)  # fresh handle reads the sidecar

    assert reopened.path("a", Subject="m01", Session=1) == Path("Z:/a.tif")
    assert (tmp_path / "raw" / "_filemap.json").is_file()


def test_discover_indexes_a_directory(tmp_path: Path) -> None:
    src = tmp_path / "acq" / "m01"
    src.mkdir(parents=True)
    (src / "ch0.tif").write_text("x", encoding="utf-8")
    (src / "ch1.tif").write_text("y", encoding="utf-8")
    (src / "notes.txt").write_text("z", encoding="utf-8")
    fm = FileMap(tmp_path / "raw", "raw", SCHEMA)

    found = fm.discover(src, pattern="*.tif", Subject="m01", Session=1)

    assert set(found) == {"ch0", "ch1"}  # notes.txt excluded by the pattern
    assert set(fm.paths(Subject="m01", Session=1)) == {"ch0", "ch1"}
    assert fm.exists(Subject="m01", Session=1) is True  # discovered files exist


def test_discover_non_directory_raises(tmp_path: Path) -> None:
    fm = FileMap(tmp_path / "raw", "raw", SCHEMA)

    with pytest.raises(NotADirectoryError):
        fm.discover(tmp_path / "missing", Subject="m01", Session=1)
