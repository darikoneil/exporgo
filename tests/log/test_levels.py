"""Tests for the LogLevel enumeration."""

from exporgo.log.levels import LogLevel


def test_log_levels_match_standard_library_values() -> None:
    assert LogLevel.NOTSET == 0
    assert LogLevel.DEBUG == 10
    assert LogLevel.INFO == 20
    assert LogLevel.WARNING == 30
    assert LogLevel.ERROR == 40
    assert LogLevel.CRITICAL == 50


def test_loguru_specific_levels_are_ordered_between_standard_levels() -> None:
    assert LogLevel.TRACE == 5
    assert LogLevel.SUCCESS == 25
    assert LogLevel.NOTSET < LogLevel.TRACE < LogLevel.DEBUG
    assert LogLevel.INFO < LogLevel.SUCCESS < LogLevel.WARNING


def test_log_level_is_int_comparable() -> None:
    assert LogLevel.ERROR > 30
    assert int(LogLevel.INFO) == 20
