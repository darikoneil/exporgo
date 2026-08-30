"""Tests for the Study container: identity, resources, validation, persistence."""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from loguru import logger

from exporgo.study import IdentityKey, ResourceSpec, Study


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


def test_resources_property_returns_specs() -> None:
    study = Study(name="s", root="D:/data", identity=["Subject"])
    study.declare_resource("beh", "{Subject}/behavior.csv")
    assert isinstance(study.resources["beh"], ResourceSpec)


def test_resource_returns_a_bound_handle_matching_path(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_resource("beh", "{Subject}/behavior.csv")

    handle = study.resource("beh")
    assert handle.path(Subject="m01") == study.path("beh", Subject="m01")


def test_resource_unknown_name_raises() -> None:
    study = Study(name="s", root="D:/data")
    with pytest.raises(KeyError):
        study.resource("nope")


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


def test_validate_checks_filemap_recorded_files_still_exist(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_filemap("raw")
    study.register(Subject="m01")  # recorded file exists -> present
    study.register(Subject="m02")  # recorded file was deleted -> missing
    study.register(Subject="m03")  # nothing recorded at all -> missing
    live = tmp_path / "a.tif"
    live.write_text("x", encoding="utf-8")
    study.filemap("raw").record(live, Subject="m01")
    study.filemap("raw").record(tmp_path / "gone.tif", Subject="m02")  # never created

    report = study.validate()
    m01 = study.identity.identity(Subject="m01")
    m02 = study.identity.identity(Subject="m02")
    m03 = study.identity.identity(Subject="m03")

    assert (m01, "raw") in report.present
    assert (m02, "raw") in report.missing
    assert (m03, "raw") in report.missing
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


def test_repr_is_unambiguous() -> None:
    study = Study(name="fomo", root="D:/data", identity=["Subject", "Session"])

    result = repr(study)

    assert result.startswith("Study(")
    assert "name='fomo'" in result
    assert "Subject" in result
    assert "Session" in result


def test_str_is_a_concise_summary() -> None:
    study = Study(name="fomo", root="D:/data", identity=["Subject"])
    study.declare_resource("raw", "{Subject}/raw")
    study.register(Subject="m01")

    text = str(study)

    assert "fomo" in text
    assert "1 resource" in text
    assert "1 identit" in text


def test_print_outputs_a_multiline_summary() -> None:
    study = Study(name="fomo", root="D:/data", identity=["Subject", "Session"])
    study.declare_resource("raw", "{Subject}/{Session}/raw")
    study.register(Subject="m01", Session=1)

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        study.print()
    out = buffer.getvalue()

    assert "fomo" in out
    assert "raw" in out
    assert "resources" in out.lower()
    assert "\n" in out


def test_first_save_logs_the_creation_date(tmp_path: Path) -> None:
    Study(name="fomo", root=tmp_path).save()

    logger.remove()  # flush + close the async file sink so the record is on disk
    content = (tmp_path / "fomo.log").read_text(encoding="utf-8")

    assert "created" in content.lower()
    assert "fomo" in content


def test_second_save_does_not_relog_created(tmp_path: Path) -> None:
    study = Study(name="fomo", root=tmp_path)
    study.save()  # first save: study.toml is created -> logs "created"
    logger.remove()  # flush + close the file sink
    (tmp_path / "fomo.log").unlink()  # isolate the second save's output

    study.save()  # study.toml already exists -> plain "saved", no "created"
    logger.remove()
    content = (tmp_path / "fomo.log").read_text(encoding="utf-8")

    assert "created" not in content.lower()
    assert "saved" in content.lower()


def test_load_logs_that_the_study_was_accessed(tmp_path: Path) -> None:
    Study(name="fomo", root=tmp_path).save()  # configures logging into fomo.log
    Study.load(tmp_path)  # emits an access record to the still-active sink

    logger.remove()  # flush
    content = (tmp_path / "fomo.log").read_text(encoding="utf-8")

    assert "accessed" in content.lower()


def test_declare_and_get_filemap(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_filemap("raw")

    assert study.filemap("raw").name == "raw"
    assert set(study.filemaps) == {"raw"}


def test_filemap_unknown_name_raises(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path)
    with pytest.raises(KeyError):
        study.filemap("nope")


def test_filemap_round_trips_through_save_load(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_filemap("raw")
    study.filemap("raw").record("Z:/a.tif", name="a", Subject="m01")
    study.save()

    loaded = Study.load(tmp_path)

    assert set(loaded.filemaps) == {"raw"}
    assert loaded.filemap("raw").templated is False
    assert loaded.filemap("raw").path("a", Subject="m01") == Path("Z:/a.tif")


def test_identities_of_a_filemap(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_filemap("raw")
    study.filemap("raw").record("Z:/a.tif", Subject="m01")

    assert study.identities(filemap="raw") == {study.identity.identity(Subject="m01")}


def test_declare_filemap_rejects_an_unknown_template_key(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    with pytest.raises(ValueError, match="unknown identity keys"):
        study.declare_filemap("s2p", root_template="{Session}/suite2p")


def test_templated_filemap_round_trips_through_save_load(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_filemap("s2p", root_template="{Subject}/suite2p")
    study.save()

    handle = Study.load(tmp_path).filemap("s2p")

    assert handle.templated is True
    assert handle.root_template == "{Subject}/suite2p"


def test_declare_and_get_dump(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_dump("reference")

    assert study.dump("reference").name == "reference"
    assert set(study.dumps) == {"reference"}


def test_dump_unknown_name_raises(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path)
    with pytest.raises(KeyError):
        study.dump("nope")


def test_dump_round_trips_through_save_load(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_dump("reference")
    study.dump("reference").record("Z:/atlas.nrrd", name="atlas")
    study.save()

    loaded = Study.load(tmp_path)

    assert set(loaded.dumps) == {"reference"}
    assert loaded.dump("reference").path("atlas") == Path("Z:/atlas.nrrd")


def test_discover_reports_present_missing_and_drift(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_resource("beh", "{Subject}/behavior.csv")
    study.register(Subject="m01")  # registered + on disk -> present
    study.register(Subject="m02")  # registered, not on disk -> missing
    for subject in ("m01", "m03"):  # m03 on disk but unregistered -> drift
        (tmp_path / subject).mkdir()
        (tmp_path / subject / "behavior.csv").write_text("x", encoding="utf-8")

    report = study.discover()
    m01 = study.identity.identity(Subject="m01")
    m02 = study.identity.identity(Subject="m02")
    m03 = study.identity.identity(Subject="m03")

    assert (m01, "beh") in report.present
    assert (m02, "beh") in report.missing
    assert (m03, "beh") in report.unregistered
    assert not report.is_complete


def test_discover_register_bootstraps_full_key_identities(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_resource("beh", "{Subject}/behavior.csv")
    for subject in ("m01", "m02"):
        (tmp_path / subject).mkdir()
        (tmp_path / subject / "behavior.csv").write_text("x", encoding="utf-8")

    report = study.discover(register=True)
    m01 = study.identity.identity(Subject="m01")
    m02 = study.identity.identity(Subject="m02")

    # the report reflects the pre-bootstrap state (both were unregistered drift)...
    assert (m01, "beh") in report.unregistered
    assert (m02, "beh") in report.unregistered
    # ...but the discovered identities are now registered
    assert set(study.entities) == {m01, m02}


def test_discover_register_leaves_subset_key_partials_unregistered(
    tmp_path: Path,
) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject", "Session"])
    study.declare_resource("geno", "{Subject}/genotype.txt")  # subset: Subject only
    (tmp_path / "m01").mkdir()
    (tmp_path / "m01" / "genotype.txt").write_text("x", encoding="utf-8")

    study.discover(register=True)

    assert study.entities == ()  # a partial identity cannot form a full (Subject, Session)


def test_coverage_to_polars_is_a_tidy_long_frame(tmp_path: Path) -> None:
    import polars as pl

    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_resource("beh", "{Subject}/behavior.csv")
    study.register(Subject="m01")  # present
    study.register(Subject="m02")  # missing
    (tmp_path / "m01").mkdir()
    (tmp_path / "m01" / "behavior.csv").write_text("x", encoding="utf-8")

    frame = study.coverage().to_polars()

    assert set(frame.columns) == {"Subject", "component", "status"}
    missing = frame.filter(pl.col("status") == "missing")
    assert missing["Subject"].to_list() == ["m02"]
    assert missing["component"].to_list() == ["beh"]


def test_coverage_to_polars_without_polars_raises_helpful_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "polars", None)  # simulate polars not installed
    study = Study(name="s", root=tmp_path, identity=["Subject"])

    with pytest.raises(ImportError, match="datastore"):
        study.coverage().to_polars()


def test_coverage_str_groups_by_status(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_resource("beh", "{Subject}/behavior.csv")
    study.register(Subject="m01")  # present
    study.register(Subject="m02")  # missing
    (tmp_path / "m01").mkdir()
    (tmp_path / "m01" / "behavior.csv").write_text("x", encoding="utf-8")

    text = str(study.coverage())

    assert "CoverageReport" in text
    assert "incomplete" in text
    assert "missing" in text
    assert "Subject=m02" in text


def test_sync_registry_registers_resource_and_filemap_identities(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_resource("beh", "{Subject}/behavior.csv")
    study.declare_filemap("raw")
    (tmp_path / "m01").mkdir()  # resource on disk -> m01
    (tmp_path / "m01" / "behavior.csv").write_text("x", encoding="utf-8")
    study.filemap("raw").record("Z:/a.tif", Subject="m02")  # filemap recorded -> m02

    newly = study.sync_registry()

    m01 = study.identity.identity(Subject="m01")
    m02 = study.identity.identity(Subject="m02")
    assert set(newly) == {m01, m02}
    assert set(study.entities) == {m01, m02}


def test_sync_registry_is_idempotent(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_resource("beh", "{Subject}/behavior.csv")
    (tmp_path / "m01").mkdir()
    (tmp_path / "m01" / "behavior.csv").write_text("x", encoding="utf-8")

    first = study.sync_registry()
    second = study.sync_registry()

    assert set(first) == {study.identity.identity(Subject="m01")}
    assert second == ()  # nothing new the second time
    assert len(study.entities) == 1


def test_sync_registry_returns_only_the_unregistered(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_resource("beh", "{Subject}/behavior.csv")
    study.register(Subject="m01")  # already registered
    for subject in ("m01", "m02"):
        (tmp_path / subject).mkdir()
        (tmp_path / subject / "behavior.csv").write_text("x", encoding="utf-8")

    newly = study.sync_registry()

    assert set(newly) == {study.identity.identity(Subject="m02")}  # m01 not re-added
    assert len(study.entities) == 2


def test_sync_registry_skips_subset_key_partials(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject", "Session"])
    study.declare_resource("geno", "{Subject}/genotype.txt")  # subset: Subject only
    (tmp_path / "m01").mkdir()
    (tmp_path / "m01" / "genotype.txt").write_text("x", encoding="utf-8")

    newly = study.sync_registry()

    assert newly == ()  # a partial identity cannot form a full (Subject, Session)
    assert study.entities == ()


def test_coverage_includes_filemaps(tmp_path: Path) -> None:
    study = Study(name="s", root=tmp_path, identity=["Subject"])
    study.declare_filemap("raw")
    study.register(Subject="m01")  # registered + recorded -> present
    study.register(Subject="m02")  # registered, never recorded -> missing
    study.filemap("raw").record("Z:/a.tif", Subject="m01")
    study.filemap("raw").record("Z:/b.tif", Subject="m03")  # unregistered

    report = study.coverage()
    m01 = study.identity.identity(Subject="m01")
    m02 = study.identity.identity(Subject="m02")
    m03 = study.identity.identity(Subject="m03")

    assert (m01, "raw") in report.present
    assert (m02, "raw") in report.missing
    assert (m03, "raw") in report.unregistered
