"""Tests for FileMap: relative-path-keyed indexes of file locations per identity."""

from pathlib import Path

import pytest

from exporgo.study import FileMap
from exporgo.study.identity import IdentityKey, IdentitySchema

SCHEMA = IdentitySchema(keys=["Subject", IdentityKey(name="Session", dtype="int")])


def _filemap(study_root: Path, *, root_template: str | None = None) -> FileMap:
    return FileMap(study_root, "raw", SCHEMA, root_template=root_template)


def _suite2p_tree(root: Path) -> None:
    """Lay down a two-plane suite2p tree with a colliding F.npy in each plane."""
    for plane in ("plane0", "plane1"):
        (root / plane).mkdir(parents=True)
        (root / plane / "F.npy").write_text("F", encoding="utf-8")
        (root / plane / "Fneu.npy").write_text("Fneu", encoding="utf-8")
    (root / "plane0" / "iscell.npy").write_text("iscell", encoding="utf-8")
    (root / "notes.txt").write_text("notes", encoding="utf-8")


# -- recorded mode: record --------------------------------------------------------------


def test_record_defaults_the_key_to_the_filename(tmp_path: Path) -> None:
    fm = _filemap(tmp_path)

    recorded = fm.record("Z:/scope/m01_s1.tif", Subject="m01", Session=1)

    assert recorded == Path("Z:/scope/m01_s1.tif")
    assert fm.path("m01_s1.tif", Subject="m01", Session=1) == Path("Z:/scope/m01_s1.tif")


def test_record_with_explicit_keys(tmp_path: Path) -> None:
    fm = _filemap(tmp_path)

    fm.record("Z:/a/ch0.tif", Subject="m01", Session=1)  # key -> "ch0.tif"
    fm.record("Z:/a/ch1.tif", name="red", Subject="m01", Session=1)

    assert fm.paths(Subject="m01", Session=1) == {
        "ch0.tif": Path("Z:/a/ch0.tif"),
        "red": Path("Z:/a/ch1.tif"),
    }


def test_paths_empty_for_an_unrecorded_identity(tmp_path: Path) -> None:
    assert _filemap(tmp_path).paths(Subject="m01", Session=1) == {}


def test_path_unknown_key_raises(tmp_path: Path) -> None:
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
    _filemap(tmp_path).record("Z:/a.tif", name="a", Subject="m01", Session=1)

    reopened = FileMap(tmp_path, "raw", SCHEMA)  # fresh handle reads the sidecar

    assert reopened.path("a", Subject="m01", Session=1) == Path("Z:/a.tif")
    assert (tmp_path / "raw" / "_filemap.json").is_file()


# -- discover: relative-path keying -----------------------------------------------------


def test_discover_keys_by_relative_path_without_collision(tmp_path: Path) -> None:
    src = tmp_path / "acq"
    _suite2p_tree(src)
    fm = _filemap(tmp_path)

    found = fm.discover(src, pattern="*.npy", Subject="m01", Session=1)

    assert set(found) == {
        "plane0/F.npy",
        "plane0/Fneu.npy",
        "plane0/iscell.npy",
        "plane1/F.npy",
        "plane1/Fneu.npy",
    }  # notes.txt excluded by the pattern; plane0/F and plane1/F both kept
    assert fm.exists(Subject="m01", Session=1) is True


def test_discover_non_directory_raises(tmp_path: Path) -> None:
    fm = _filemap(tmp_path)

    with pytest.raises(NotADirectoryError):
        fm.discover(tmp_path / "missing", Subject="m01", Session=1)


def test_discover_reconciles_dropped_files(tmp_path: Path) -> None:
    src = tmp_path / "acq"
    _suite2p_tree(src)
    fm = _filemap(tmp_path)
    fm.discover(src, pattern="*.npy", Subject="m01", Session=1)

    (src / "plane1" / "F.npy").unlink()
    fm.discover(src, pattern="*.npy", Subject="m01", Session=1)  # re-index

    assert "plane1/F.npy" not in fm.paths(Subject="m01", Session=1)
    assert "plane0/F.npy" in fm.paths(Subject="m01", Session=1)


# -- retrieval: the *-dispatch ----------------------------------------------------------


def test_path_exact_relative_key(tmp_path: Path) -> None:
    src = tmp_path / "acq"
    _suite2p_tree(src)
    fm = _filemap(tmp_path)
    fm.discover(src, pattern="*.npy", Subject="m01", Session=1)

    assert fm.path("plane0/F.npy", Subject="m01", Session=1) == src / "plane0" / "F.npy"


def test_path_glob_substring_finds_the_file(tmp_path: Path) -> None:
    src = tmp_path / "acq"
    _suite2p_tree(src)
    fm = _filemap(tmp_path)
    fm.discover(src, pattern="*.npy", Subject="m01", Session=1)

    assert fm.path("*iscell*", Subject="m01", Session=1) == src / "plane0" / "iscell.npy"


def test_path_ambiguous_glob_raises(tmp_path: Path) -> None:
    src = tmp_path / "acq"
    _suite2p_tree(src)
    fm = _filemap(tmp_path)
    fm.discover(src, pattern="*.npy", Subject="m01", Session=1)

    with pytest.raises(ValueError, match="ambiguous"):
        fm.path("*/F.npy", Subject="m01", Session=1)  # plane0/F and plane1/F


def test_path_glob_no_match_raises(tmp_path: Path) -> None:
    src = tmp_path / "acq"
    _suite2p_tree(src)
    fm = _filemap(tmp_path)
    fm.discover(src, pattern="*.npy", Subject="m01", Session=1)

    with pytest.raises(KeyError):
        fm.path("*.mat", Subject="m01", Session=1)


def test_paths_glob_filters(tmp_path: Path) -> None:
    src = tmp_path / "acq"
    _suite2p_tree(src)
    fm = _filemap(tmp_path)
    fm.discover(src, Subject="m01", Session=1)  # every file, no pattern

    assert set(fm.paths("plane0/*", Subject="m01", Session=1)) == {
        "plane0/F.npy",
        "plane0/Fneu.npy",
        "plane0/iscell.npy",
    }
    assert set(fm.paths("*.txt", Subject="m01", Session=1)) == {"notes.txt"}


# -- templated mode ---------------------------------------------------------------------


def test_templated_discover_derives_the_root(tmp_path: Path) -> None:
    _suite2p_tree(tmp_path / "m01" / "1" / "suite2p")
    fm = FileMap(tmp_path, "s2p", SCHEMA, root_template="{Subject}/{Session}/suite2p")

    found = fm.discover(pattern="*.npy", Subject="m01", Session=1)  # no directory passed

    assert "plane0/F.npy" in found
    assert fm.path("plane0/F.npy", Subject="m01", Session=1) == (
        tmp_path / "m01" / "1" / "suite2p" / "plane0" / "F.npy"
    )


def test_templated_discover_rejects_a_directory(tmp_path: Path) -> None:
    fm = FileMap(tmp_path, "s2p", SCHEMA, root_template="{Subject}/{Session}/suite2p")

    with pytest.raises(ValueError, match="templated"):
        fm.discover(tmp_path, Subject="m01", Session=1)


def test_recorded_discover_needs_a_directory_first(tmp_path: Path) -> None:
    fm = _filemap(tmp_path)  # recorded, nothing indexed yet

    with pytest.raises(ValueError, match="no root"):
        fm.discover(Subject="m01", Session=1)


def test_recorded_rediscover_reuses_the_stored_root(tmp_path: Path) -> None:
    src = tmp_path / "acq"
    _suite2p_tree(src)
    fm = _filemap(tmp_path)
    fm.discover(src, pattern="*.npy", Subject="m01", Session=1)

    (src / "plane0" / "new.npy").write_text("new", encoding="utf-8")
    fm.discover(Subject="m01", Session=1)  # no directory: reuse the stored root

    assert "plane0/new.npy" in fm.paths(Subject="m01", Session=1)
