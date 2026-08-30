"""Tests for the exporgo.log public surface and silent-by-default behavior."""

import io

from loguru import logger

from exporgo import log
from exporgo.log import (
    LogLevel,
    init_logger,
    log_class,
    log_function_call,
    log_major_function_call,
    read_log,
    reset_tqdm,
)


def test_public_names_are_exported() -> None:
    assert set(log.__all__) == {
        "LogLevel",
        "init_logger",
        "read_log",
        "reset_tqdm",
        "log_function_call",
        "log_major_function_call",
        "log_class",
    }
    for name in log.__all__:
        assert hasattr(log, name)


def test_all_public_callables_are_importable() -> None:
    assert LogLevel.INFO == 20
    for symbol in (
        init_logger,
        read_log,
        reset_tqdm,
        log_function_call,
        log_major_function_call,
        log_class,
    ):
        assert callable(symbol)


def test_exporgo_namespace_is_disabled_until_enabled() -> None:
    captured = io.StringIO()
    sink_id = logger.add(captured, level=0, format="{message}")
    try:
        logger.disable("exporgo")  # exporgo/__init__ does this at import; be explicit
        log_class(object(), level=LogLevel.INFO)
        assert captured.getvalue() == ""

        logger.enable("exporgo")
        log_class(object(), level=LogLevel.INFO)
        assert "object:" in captured.getvalue()
    finally:
        logger.remove(sink_id)
        logger.disable("exporgo")
