"""Reusable :mod:`loguru`-based logging framework for exporgo.

This subpackage is the base layer of exporgo: a logging framework any project can
drive via :func:`init_logger`, plus decorators that record calls, arguments, return
values, and timing.

Example:
    >>> from exporgo.log import init_logger, log_function_call, LogLevel
    >>> init_logger(name="my_project", log_level_console=LogLevel.DEBUG)
    >>> @log_function_call()
    ... def add(left, right):
    ...     return left + right
"""

from exporgo.log.decorators import (
    log_class,
    log_function_call,
    log_major_function_call,
)
from exporgo.log.levels import LogLevel
from exporgo.log.sinks import init_logger, read_log, reset_tqdm

__all__ = [
    "LogLevel",
    "init_logger",
    "log_class",
    "log_function_call",
    "log_major_function_call",
    "read_log",
    "reset_tqdm",
]
