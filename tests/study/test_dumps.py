"""Tests for Dump: a study-global, relative-path-keyed index of file locations."""

from pathlib import Path

import pytest

from exporgo.study import Dump


def _dump(root: Path) -> Dump:
    return Dump(root / "reference", "reference")


def test_record_defaults_the_key_to_the_filename(tmp_path: Path) -> None:
    dump = _dump(tmp_path)

    recorded = dump.record("Z:/atlases/ccf.nrrd")

    assert recorded == Path("Z:/atlases/ccf.nrrd")
    assert dump.path("ccf.nrrd") == Path("Z:/atlases/ccf.nrrd")


def test_record_with_an_explicit_key(tmp_path: Path) -> None:
    dump = _dump(tmp_path)

    dump.record("Z:/atlases/ccf.nrrd", name="atlas")

    assert dump.paths() == {"atlas": Path("Z:/atlases/ccf.nrrd")}


def test_discover_keys_by_relative_path(tmp_path: Path) -> None:
    src = tmp_path / "shared"
    (src / "atlas").mkdir(parents=True)
    (src / "atlas" / "ccf.nrrd").write_text("ccf", encoding="utf-8")
    (src / "README.md").write_text("readme", encoding="utf-8")
    dump = _dump(tmp_path)

    found = dump.discover(src)

    assert set(found) == {"atlas/ccf.nrrd", "README.md"}
    assert dump.path("*ccf*") == src / "atlas" / "ccf.nrrd"


def test_discover_defaults_to_its_own_directory(tmp_path: Path) -> None:
    dump = _dump(tmp_path)
    dump.directory.mkdir(parents=True)
    (dump.directory / "ccf.nrrd").write_text("ccf", encoding="utf-8")

    found = dump.discover()

    assert set(found) == {"ccf.nrrd"}


def test_discover_ignores_its_own_sidecar(tmp_path: Path) -> None:
    dump = _dump(tmp_path)
    dump.record("Z:/atlases/ccf.nrrd", name="atlas")
    (dump.directory / "readme.md").write_text("readme", encoding="utf-8")

    found = dump.discover()

    assert "_dump.json" not in found
    assert set(found) == {"readme.md"}


def test_exists_reflects_the_filesystem(tmp_path: Path) -> None:
    dump = _dump(tmp_path)
    real = tmp_path / "atlas.nrrd"
    dump.record(real)

    assert dump.exists() is False
    real.write_text("x", encoding="utf-8")
    assert dump.exists() is True


def test_records_persist_across_instances(tmp_path: Path) -> None:
    _dump(tmp_path).record("Z:/atlases/ccf.nrrd", name="atlas")

    reopened = Dump(tmp_path / "reference", "reference")

    assert reopened.path("atlas") == Path("Z:/atlases/ccf.nrrd")
    assert (tmp_path / "reference" / "_dump.json").is_file()


def test_path_unknown_key_raises(tmp_path: Path) -> None:
    dump = _dump(tmp_path)
    dump.record("Z:/atlases/ccf.nrrd", name="atlas")

    with pytest.raises(KeyError):
        dump.path("nope")


def test_discover_non_directory_raises(tmp_path: Path) -> None:
    dump = _dump(tmp_path)

    with pytest.raises(NotADirectoryError):
        dump.discover(tmp_path / "missing")


def test_path_ambiguous_glob_raises(tmp_path: Path) -> None:
    src = tmp_path / "shared"
    for plane in ("plane0", "plane1"):
        (src / plane).mkdir(parents=True)
        (src / plane / "F.npy").write_text("F", encoding="utf-8")
    dump = _dump(tmp_path)
    dump.discover(src)

    with pytest.raises(ValueError, match="ambiguous"):
        dump.path("*/F.npy")  # plane0/F and plane1/F


def test_path_glob_no_match_raises(tmp_path: Path) -> None:
    src = tmp_path / "shared"
    src.mkdir()
    (src / "ccf.nrrd").write_text("ccf", encoding="utf-8")
    dump = _dump(tmp_path)
    dump.discover(src)

    with pytest.raises(KeyError):
        dump.path("*.mat")
