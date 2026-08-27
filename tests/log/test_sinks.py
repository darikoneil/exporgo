"""Tests for sink construction and the parameterized init_logger entry point."""

from pathlib import Path

import pytest

import exporgo.log.sinks as sinks
from exporgo.log.levels import LogLevel


# --------------------------------------------------------------------------- filters
@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (LogLevel.DEBUG, False),
        (LogLevel.INFO, True),
        (LogLevel.WARNING, True),
        (LogLevel.ERROR, False),
    ],
)
def test_primary_filter_accepts_only_info_and_warning(level, expected, make_record):  # noqa: ANN001
    assert sinks._is_primary_log(make_record(level)) is expected


def test_exception_filter_requires_exception_information(make_record):  # noqa: ANN001
    assert not sinks._exception_only_filter(make_record(LogLevel.ERROR))
    assert sinks._exception_only_filter(
        make_record(LogLevel.ERROR, exception=ValueError("boom"))
    )


def test_specific_filter_uses_inclusive_minimum_level(make_record):  # noqa: ANN001
    warning_or_higher = sinks._specific_filter(LogLevel.WARNING)

    assert not warning_or_higher(make_record(LogLevel.INFO))
    assert warning_or_higher(make_record(LogLevel.WARNING))
    assert warning_or_higher(make_record(LogLevel.ERROR))


# ---------------------------------------------------------------------- sink builders
def test_init_log_subdir_is_idempotent(tmp_path: Path) -> None:
    expected = tmp_path / "nested" / ".logs"

    assert sinks._init_log_subdir(tmp_path / "nested") == expected
    assert sinks._init_log_subdir(tmp_path / "nested") == expected
    assert expected.is_dir()


def test_primary_log_sink_uses_stem_and_expected_options(
    monkeypatch, recording_logger, tmp_path: Path
):  # noqa: ANN001
    monkeypatch.setattr(sinks, "logger", recording_logger)

    sinks._set_primary_log(tmp_path, "proj")

    sink, options = recording_logger.sinks[0]
    assert sink == str(tmp_path / "proj.log")
    assert options == {
        "enqueue": True,
        "level": LogLevel.INFO.value,
        "format": sinks.PRIMARY_FILE_FORMAT,
        "filter": sinks._is_primary_log,
        "rotation": "100 MB",
        "retention": "100 years",
        "delay": False,
    }


def test_exception_log_sink_uses_stem_and_expected_options(
    monkeypatch, recording_logger, tmp_path: Path
):  # noqa: ANN001
    monkeypatch.setattr(sinks, "logger", recording_logger)

    sinks._set_exceptions_log(tmp_path, "proj")

    sink, options = recording_logger.sinks[0]
    assert sink == str(tmp_path / ".logs" / ".proj_exception.log")
    assert (tmp_path / ".logs").is_dir()
    assert options == {
        "enqueue": True,
        "level": LogLevel.ERROR.value,
        "filter": sinks._exception_only_filter,
        "backtrace": True,
        "diagnose": True,
        "catch": True,
        "rotation": "100 MB",
        "retention": "1 week",
        "delay": True,
    }


def test_custom_log_sink_configuration_and_threshold_filter(
    monkeypatch, recording_logger, tmp_path: Path
):  # noqa: ANN001
    monkeypatch.setattr(sinks, "logger", recording_logger)

    sinks._set_custom_log(tmp_path, LogLevel.DEBUG, "proj", retention="2 days")

    sink, options = recording_logger.sinks[0]
    assert sink == str(tmp_path / ".logs" / ".proj_DEBUG.log")
    assert options["enqueue"] is True
    assert options["level"] == LogLevel.DEBUG.value
    assert options["rotation"] == "100 MB"
    assert options["retention"] == "2 days"


# ------------------------------------------------------------------------ init_logger
def test_init_logger_enables_named_namespace_and_adds_console_sink(
    monkeypatch, recording_logger
):  # noqa: ANN001
    monkeypatch.setattr(sinks, "logger", recording_logger)

    sinks.init_logger(name="proj", log_level_console=LogLevel.WARNING)

    assert recording_logger.enabled == ["proj"]
    assert recording_logger.remove_calls == 1
    assert recording_logger.sinks == [
        (
            sinks.stderr,
            {
                "colorize": True,
                "format": sinks.CONSOLE_FORMAT,
                "level": LogLevel.WARNING.value,
            },
        )
    ]


def test_init_logger_without_name_enables_all_namespaces(
    monkeypatch, recording_logger
):  # noqa: ANN001
    monkeypatch.setattr(sinks, "logger", recording_logger)

    sinks.init_logger()

    assert recording_logger.enabled == [""]


def test_init_logger_configures_all_file_sinks_with_stem(
    monkeypatch, recording_logger, tmp_path: Path
):  # noqa: ANN001
    calls: list[tuple] = []
    monkeypatch.setattr(sinks, "logger", recording_logger)
    monkeypatch.setattr(
        sinks, "_set_primary_log", lambda base, stem: calls.append(("primary", base, stem))
    )
    monkeypatch.setattr(
        sinks,
        "_set_exceptions_log",
        lambda base, stem: calls.append(("exceptions", base, stem)),
    )
    monkeypatch.setattr(
        sinks,
        "_set_custom_log",
        lambda base, level, stem: calls.append(("custom", base, level, stem)),
    )

    sinks.init_logger(
        name="proj", base_directory=tmp_path, log_level_custom=LogLevel.DEBUG
    )

    assert calls == [
        ("primary", tmp_path, "proj"),
        ("exceptions", tmp_path, "proj"),
        ("custom", tmp_path, LogLevel.DEBUG, "proj"),
    ]


def test_init_logger_file_stem_defaults_to_exporgo_when_unnamed(
    monkeypatch, recording_logger, tmp_path: Path
):  # noqa: ANN001
    stems: list[str] = []
    monkeypatch.setattr(sinks, "logger", recording_logger)
    monkeypatch.setattr(sinks, "_set_primary_log", lambda base, stem: stems.append(stem))  # noqa: ARG005
    monkeypatch.setattr(sinks, "_set_exceptions_log", lambda base, stem: None)  # noqa: ARG005

    sinks.init_logger(base_directory=tmp_path)

    assert stems == ["exporgo"]


def test_init_logger_file_stem_override(
    monkeypatch, recording_logger, tmp_path: Path
):  # noqa: ANN001
    stems: list[str] = []
    monkeypatch.setattr(sinks, "logger", recording_logger)
    monkeypatch.setattr(sinks, "_set_primary_log", lambda base, stem: stems.append(stem))  # noqa: ARG005
    monkeypatch.setattr(sinks, "_set_exceptions_log", lambda base, stem: None)  # noqa: ARG005

    sinks.init_logger(name="proj", base_directory=tmp_path, file_stem="run7")

    assert stems == ["run7"]


def test_init_logger_warns_for_custom_sink_without_directory(
    monkeypatch, recording_logger
):  # noqa: ANN001
    monkeypatch.setattr(sinks, "logger", recording_logger)

    with pytest.warns(UserWarning, match="without.*base directory"):
        sinks.init_logger(log_level_custom=LogLevel.DEBUG)

    assert len(recording_logger.sinks) == 1


# -------------------------------------------------------------------------- reset_tqdm
def test_reset_tqdm_adds_a_write_sink(monkeypatch, recording_logger):  # noqa: ANN001
    monkeypatch.setattr(sinks, "logger", recording_logger)

    sinks.reset_tqdm()

    sink, options = recording_logger.sinks[0]
    assert callable(sink)
    assert options["colorize"] is True
    assert options["level"] == LogLevel.INFO.value
