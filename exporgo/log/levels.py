"""Log severity levels shared by exporgo's sinks and decorators."""

from enum import IntEnum
from logging import CRITICAL, DEBUG, ERROR, INFO, NOTSET, WARNING

__all__ = ["LogLevel"]


class LogLevel(IntEnum):
    """Log severity levels.

    Values match :mod:`logging`'s numeric levels where they overlap (e.g. ``INFO``
    is 20) and add Loguru's ``TRACE`` (5) and ``SUCCESS`` (25) levels in between, so
    a single enum can configure both Loguru sinks and any standard-library-based
    tooling.

    Because the enum subclasses :class:`int`, members compare directly against the
    numeric levels used by both :mod:`logging` and :mod:`loguru`.
    """

    NOTSET = NOTSET  # 0
    TRACE = 5  # Loguru trace level
    DEBUG = DEBUG  # 10
    INFO = INFO  # 20
    SUCCESS = 25  # Loguru success level
    WARNING = WARNING  # 30
    ERROR = ERROR  # 40
    CRITICAL = CRITICAL  # 50
