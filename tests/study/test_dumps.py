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
