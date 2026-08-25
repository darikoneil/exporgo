"""Tests for the Study container: identity, resources, validation, persistence."""

from pathlib import Path

import pytest

from exporgo.study import IdentityKey, Study


def test_study_defaults_identity_to_subject() -> None:
    study = Study(name="s", root="D:/data")
    assert study.identity.names == ("Subject",)


def test_study_accepts_custom_identity_keys() -> None:
    study = Study(name="s", root="D:/data", identity=["Subject", "Session"])
    assert study.identity.names == ("Subject", "Session")


def test_register_adds_and_dedupes_entities() -> None:
    study = Study(name="s", root="D:/data", identity=["Subject", "Session"])
    study.register(Subject="m01", Session=1)
    study.register(Subject="m01", Session=1)  # duplicate
    study.register(Subject="m02", Session=1)
    assert len(study.entities) == 2


def test_declare_resource_rejects_unknown_identity_key() -> None:
    study = Study(name="s", root="D:/data", identity=["Subject"])
    with pytest.raises(ValueError, match="Session"):
        study.declare_resource("beh", "{Subject}/{Session}/behavior.csv")


def test_path_resolves_a_declared_resource() -> None:
    study = Study(name="s", root="D:/data", identity=["Subject"])
    study.declare_resource("beh", "{Subject}/behavior.csv")
    assert study.path("beh", Subject="m01") == Path("D:/data/m01/behavior.csv")


def test_path_unknown_resource_raises() -> None:
    study = Study(name="s", root="D:/data")
    with pytest.raises(KeyError):
        study.path("nope", Subject="m01")


def test_validate_reports_present_and_missing(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_resource("beh", "{Subject}/behavior.csv")
    study.register(Subject="m01")
    study.register(Subject="m02")
    (tmp_path / "m01").mkdir()
    (tmp_path / "m01" / "behavior.csv").write_text("x", encoding="utf-8")

    report = study.validate()

    m01 = study.identity.identity(Subject="m01")
    m02 = study.identity.identity(Subject="m02")
    assert (m01, "beh") in report.present
    assert (m02, "beh") in report.missing
    assert not report.is_complete


def test_save_initializes_logging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save() wires logging into the study root via init_logger (file_stem = name)."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "exporgo.study.study.init_logger", lambda **kwargs: calls.append(kwargs)
    )

    Study(name="fomo", root=tmp_path).save()

    assert len(calls) == 1
    assert calls[0]["base_directory"] == tmp_path
    assert calls[0]["file_stem"] == "fomo"


def test_load_does_not_initialize_logging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Loading a study is side-effect-free: it does not reconfigure logging."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "exporgo.study.study.init_logger", lambda **kwargs: calls.append(kwargs)
    )

    Study(name="fomo", root=tmp_path).save()
    assert len(calls) == 1  # save wired logging
    calls.clear()

    Study.load(tmp_path)
    assert calls == []  # load did not


def test_save_creates_a_real_log_file(tmp_path: Path) -> None:
    """End-to-end: save() leaves a real ``<root>/<name>.log`` on disk."""
    Study(name="fomo", root=tmp_path).save()

    assert (tmp_path / "fomo.log").is_file()


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    study = Study(
        name="fomo",
        root=tmp_path,
        identity=["Subject", IdentityKey(name="Session", dtype="int")],
    )
    study.declare_resource("beh", "{Subject}/{Session}/behavior.csv")
    study.register(Subject="m01", Session=1)
    study.register(Subject="m02", Session=2)

    saved = study.save()
    assert saved == tmp_path / "study.toml"

    loaded = Study.load(tmp_path)
    assert loaded.name == "fomo"
    assert loaded.identity.names == ("Subject", "Session")
    assert loaded.identity.keys[1].dtype == "int"
    assert loaded.entities == study.entities
    assert loaded.resources["beh"].template == "{Subject}/{Session}/behavior.csv"
