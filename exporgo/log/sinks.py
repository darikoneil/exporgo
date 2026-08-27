"""Console and rotating-file sinks, and the ``init_logger`` entry point.

:func:`init_logger` is parameterized by the package ``name`` to enable and the
``file_stem`` used for log filenames, so any project can drive the same framework
(e.g. ``init_logger(name="my_project", base_directory=path)``).
"""

from collections.abc import Callable
from pathlib import Path
from sys import stderr
from typing import TYPE_CHECKING
from warnings import warn

from loguru import logger

from exporgo.log.levels import LogLevel

if TYPE_CHECKING:
    from loguru import Record

__all__ = ["init_logger", "reset_tqdm"]


CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | "
    "<level>{message}</level>"
)
"""Loguru format for the colorized console sink: timestamp, level, message."""

PRIMARY_FILE_FORMAT = "{time}\t{level}\n\t{message}"
"""Loguru format for the primary (INFO/WARNING) rotating log file."""


def _exception_only_filter(record: "Record") -> bool:
    """Keep only log records that carry exception information."""
    return record["exception"] is not None


def _is_primary_log(record: "Record") -> bool:
    """Keep only ``INFO`` and ``WARNING`` records, for the primary log file."""
    return record["level"].no in {LogLevel.INFO.value, LogLevel.WARNING.value}


def _specific_filter(log_level: LogLevel) -> Callable[["Record"], bool]:
    """Create a threshold filter accepting records at or above ``log_level``."""

    def _inner_filter(record: "Record") -> bool:
        """Accept records whose level meets or exceeds the threshold."""
        return record["level"].no >= log_level

    return _inner_filter


def _init_log_subdir(log_base: Path) -> Path:
    """Ensure the hidden ``.logs`` subdirectory exists and return its path."""
    log_directory = log_base.joinpath(".logs")
    log_directory.mkdir(exist_ok=True, parents=True)
    return log_directory


def _set_primary_log(base_directory: Path, file_stem: str) -> None:
    """Attach the primary rotating sink (``<stem>.log``) for INFO/WARNING records."""
    log_file = base_directory.joinpath(f"{file_stem}.log")
    logger.add(
        str(log_file),
        enqueue=True,
        level=LogLevel.INFO.value,
        format=PRIMARY_FILE_FORMAT,
        filter=_is_primary_log,
        rotation="100 MB",
        retention="100 years",
        delay=False,
    )


def _set_exceptions_log(base_directory: Path, file_stem: str) -> None:
    """Attach an exceptions-only sink (``.logs/.<stem>_exception.log``)."""
    log_directory = _init_log_subdir(base_directory)
    log_file = log_directory.joinpath(f".{file_stem}_exception.log")
    logger.add(
        str(log_file),
        enqueue=True,
        level=LogLevel.ERROR.value,
        filter=_exception_only_filter,
        backtrace=True,
        diagnose=True,
        catch=True,
        rotation="100 MB",
        retention="1 week",
        delay=True,
    )


def _set_custom_log(
    base_directory: Path,
    log_level: LogLevel,
    file_stem: str,
    *,
    retention: str = "1 week",
) -> None:
    """Attach a sink filtered to a single caller-specified threshold level."""
    log_directory = _init_log_subdir(base_directory)
    log_file = log_directory.joinpath(f".{file_stem}_{log_level.name}.log")
    logger.add(
        str(log_file),
        enqueue=True,
        level=log_level.value,
        filter=_specific_filter(log_level),
        rotation="100 MB",
        retention=retention,
    )


def init_logger(
    *,
    name: str | None = None,
    base_directory: Path | None = None,
    log_level_console: LogLevel = LogLevel.INFO,
    log_level_custom: LogLevel | None = None,
    file_stem: str | None = None,
) -> None:
    """Configure and enable logging for a project.

    Enables the given logger ``name`` (or all namespaces when ``name`` is ``None``),
    clears existing sinks, and attaches a colorized console sink. If ``base_directory``
    is given, also attaches the primary rotating file sink (``<stem>.log``,
    INFO/WARNING) and an exceptions sink (``.logs/.<stem>_exception.log``), plus an
    optional third sink filtered to ``log_level_custom``. Because it removes existing
    sinks first, it reconfigures logging cleanly and is safe to call more than once
    (idempotent).

    Args:
        name: Loguru namespace to enable (typically the consuming package). When
            ``None``, all namespaces are enabled.
        base_directory: Directory for log files. If ``None``, only the console sink
            is configured.
        log_level_console: Minimum level shown on the console.
        log_level_custom: If given (and ``base_directory`` is set), adds a file sink
            capturing records at or above this threshold.
        file_stem: Base name for log files; defaults to ``name`` or ``"exporgo"``.

    Warning:
        If ``log_level_custom`` is given without ``base_directory``, a
        :class:`UserWarning` is issued and no custom sink is created, since there is
        nowhere to write it.

    Example:
        >>> from pathlib import Path
        >>> from exporgo.log import LogLevel, init_logger
        >>> init_logger(
        ...     name="my_project",
        ...     base_directory=Path("logs"),
        ...     log_level_console=LogLevel.DEBUG,
        ... )
    """
    logger.enable(name if name is not None else "")
    logger.remove()
    logger.add(
        stderr, colorize=True, format=CONSOLE_FORMAT, level=log_level_console.value
    )

    stem = file_stem if file_stem is not None else (name or "exporgo")

    if base_directory is not None:
        _set_primary_log(base_directory, stem)
        _set_exceptions_log(base_directory, stem)

    if log_level_custom is not None:
        if base_directory is None:
            msg = "Cannot set custom log level without specifying base directory"
            warn(msg, stacklevel=2)
        else:
            _set_custom_log(base_directory, log_level_custom, stem)


def reset_tqdm(*, level: LogLevel = LogLevel.INFO) -> None:
    """Add a ``tqdm``-compatible console sink so progress bars and logs coexist.

    Args:
        level: Minimum level for the tqdm sink.

    Raises:
        ImportError: If the optional ``tqdm`` dependency is not installed.
    """
    try:
        from tqdm import tqdm
    except ImportError as error:
        msg = "reset_tqdm requires the optional 'tqdm' dependency."
        raise ImportError(msg) from error

    logger.add(
        lambda message: tqdm.write(message, end=""),
        colorize=True,
        level=level.value,
    )
