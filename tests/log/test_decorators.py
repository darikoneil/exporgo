"""Tests for the logging decorators and their reporting helpers."""

import numpy as np
import pytest

import exporgo.log.decorators as decorators
from exporgo.log.levels import LogLevel
from exporgo.log.rendering import _LOG_ELEMENT_LIMIT, render_object


# ------------------------------------------------------------------- reporting helpers
def test_report_call_renders_positional_and_keyword_values(recording_logger):  # noqa: ANN001
    decorators._report_call(
        recording_logger,
        "analyze",
        LogLevel.DEBUG,
        args=(np.zeros(2),),
        kwargs={"threshold": 0.5},
    )

    assert recording_logger.entries[0][0] == "DEBUG"
    message = recording_logger.entries[0][1][0]
    assert "Called 'analyze'" in message
    assert "Numpy array of shape (2,) and dtype float64" in message
    assert "threshold" in message
    assert "0.5" in message


def test_report_return_expands_short_tuple(recording_logger):  # noqa: ANN001
    decorators._report_return(
        recording_logger, "split", LogLevel.SUCCESS, result=(np.zeros(1), [1, 2])
    )

    assert recording_logger.entries[0][0] == "SUCCESS"
    message = recording_logger.entries[0][1][0]
    assert "Returned 'split'" in message
    assert "Numpy array of shape (1,) and dtype float64" in message
    assert "list of length 2" in message


@pytest.mark.parametrize(
    "result",
    [
        tuple(range(_LOG_ELEMENT_LIMIT)),
        "single-result",
    ],
)
def test_report_return_uses_single_renderer_for_other_results(recording_logger, result):  # noqa: ANN001
    decorators._report_return(recording_logger, "compute", LogLevel.INFO, result=result)

    expected = f"Returned 'compute' with values:\n\t{render_object(result)}"
    assert recording_logger.entries == [("INFO", (expected,))]


# ------------------------------------------------------------------------- decorators
def test_log_function_call_preserves_metadata_and_returns_value(
    monkeypatch, recording_logger
):  # noqa: ANN001
    monkeypatch.setattr(decorators, "logger", recording_logger)

    @decorators.log_function_call(level=LogLevel.DEBUG)
    def add(left: int, right: int = 1) -> int:
        """Add two numbers."""
        return left + right

    assert add(2, right=3) == 5
    assert add.__name__ == "add"
    assert add.__doc__ == "Add two numbers."
    assert recording_logger.opt_depths == [1]
    assert [entry[0] for entry in recording_logger.entries] == ["DEBUG", "DEBUG"]
    assert "Called 'add'" in recording_logger.entries[0][1][0]
    assert "Returned 'add'" in recording_logger.entries[1][1][0]


def test_log_major_function_call_records_timing_and_result(
    monkeypatch, recording_logger
):  # noqa: ANN001
    times = iter([10.0, 12.5])
    monkeypatch.setattr(decorators, "logger", recording_logger)
    monkeypatch.setattr(decorators, "time", lambda: next(times))

    @decorators.log_major_function_call(
        timing_level=LogLevel.INFO,
        args_level=LogLevel.TRACE,
        rets_level=LogLevel.SUCCESS,
    )
    def multiply(value: int, *, factor: int) -> int:
        return value * factor

    assert multiply(4, factor=3) == 12
    assert recording_logger.opt_depths == [1]
    assert [entry[0] for entry in recording_logger.entries] == [
        "INFO",
        "TRACE",
        "INFO",
        "SUCCESS",
    ]
    assert recording_logger.entries[0][1] == ("Called '{}'", "multiply")
    assert recording_logger.entries[2][1] == ("'{}' returned in '{}' ", "multiply", 2.5)


def test_log_class_reports_class_name_and_value(monkeypatch, recording_logger):  # noqa: ANN001
    monkeypatch.setattr(decorators, "logger", recording_logger)

    class _Parameters:
        def __str__(self) -> str:
            return "alpha=0.5"

    decorators.log_class(_Parameters(), level=LogLevel.WARNING)

    assert recording_logger.entries == [("WARNING", ("_Parameters:\nalpha=0.5",))]
