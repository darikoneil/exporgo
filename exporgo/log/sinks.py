"""Console and rotating-file sinks, the ``init_logger`` entry point, and a log reader.

:func:`init_logger` is parameterized by the package ``name`` to enable and the ``file_stem``
used for log filenames, so any project can drive the same framework (e.g.
``init_logger(name="my_project", base_directory=path)``).

Each writer -- a process on a host -- logs into its **own** directory,
``<base>/.logs/<host>_<user>_<pid>/``, rather than a single shared file. Independent writers,
even on different machines sharing a study over a network filesystem, therefore never write the
same file, so there is no interleaving, no rotation race, and no permission clash. :func:`read_log`
merges every writer's log back into one chronological view.
"""

import getpass
import os
import re
import socket
from collections.abc import Callable
from pathlib import Path
from sys import stderr
from typing import TYPE_CHECKING
from warnings import warn

from loguru import logger

from exporgo.log.levels import LogLevel

if TYPE_CHECKING:
    from loguru import Record

__all__ = ["init_logger", "read_log", "reset_tqdm"]


CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | "
    "<level>{message}</level>"
)
"""Loguru format for the colorized console sink: timestamp, level, message."""

PRIMARY_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS!UTC}\t{level}\n\t{message}"
"""Loguru format for the primary (INFO/WARNING) rotating log file.

The timestamp is a fixed-width UTC value so records from different writers sort chronologically
by a plain lexical comparison (see :func:`read_log`), regardless of each host's local timezone.
"""

_LOGS_DIRNAME = ".logs"
_RECORD_START = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


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


def _writer_tag() -> str:
    """Return this writer's discriminator ``<host>_<user>_<pid>`` (filesystem-safe).

    Uniquely identifies a live writer (a process on a host), so no two concurrent writers ever
    resolve to the same log file. Host and user cannot always be determined; each falls back to
    a placeholder rather than failing.
    """
    try:
        host = socket.gethostname()
    except OSError:
        host = "host"
    try:
        user = getpass.getuser()
    except (OSError, KeyError):
        user = "user"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", f"{host}_{user}_{os.getpid()}")


def _writer_log_directory(base_directory: Path) -> Path:
    """Return (creating) this writer's own log directory ``<base>/.logs/<host>_<user>_<pid>``."""
    directory = base_directory / _LOGS_DIRNAME / _writer_tag()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _set_primary_log(log_directory: Path, file_stem: str) -> None:
    """Attach the primary rotating sink (``<stem>.log``) for INFO/WARNING records."""
    log_file = log_directory.joinpath(f"{file_stem}.log")
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


def _set_exceptions_log(log_directory: Path, file_stem: str) -> None:
    """Attach an exceptions-only sink (``<stem>.exception.log``)."""
    log_file = log_directory.joinpath(f"{file_stem}.exception.log")
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
    log_directory: Path,
    log_level: LogLevel,
    file_stem: str,
    *,
    retention: str = "1 week",
) -> None:
    """Attach a sink filtered to a single caller-specified threshold level."""
    log_file = log_directory.joinpath(f"{file_stem}.{log_level.name}.log")
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

    Enables the given logger ``name`` (or all namespaces when ``name`` is ``None``), clears
    existing sinks, and attaches a colorized console sink. If ``base_directory`` is given, also
    attaches the primary rotating file sink (``<stem>.log``, INFO/WARNING) and an exceptions
    sink (``<stem>.exception.log``), plus an optional third sink filtered to ``log_level_custom``
    -- all inside this writer's own directory, ``<base>/.logs/<host>_<user>_<pid>/``, so
    concurrent writers never share a file. Because it removes existing sinks first, it
    reconfigures logging cleanly and is safe to call more than once (idempotent).

    Args:
        name: Loguru namespace to enable (typically the consuming package). When ``None``, all
            namespaces are enabled.
        base_directory: Directory for log files. If ``None``, only the console sink is
            configured.
        log_level_console: Minimum level shown on the console.
        log_level_custom: If given (and ``base_directory`` is set), adds a file sink capturing
            records at or above this threshold.
        file_stem: Base name for log files; defaults to ``name`` or ``"exporgo"``.

    Warning:
        If ``log_level_custom`` is given without ``base_directory``, a :class:`UserWarning` is
        issued and no custom sink is created, since there is nowhere to write it.

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

    log_directory = (
        _writer_log_directory(base_directory) if base_directory is not None else None
    )
    if log_directory is not None:
        _set_primary_log(log_directory, stem)
        _set_exceptions_log(log_directory, stem)

    if log_level_custom is not None:
        if log_directory is None:
            msg = "Cannot set custom log level without specifying base directory"
            warn(msg, stacklevel=2)
        else:
            _set_custom_log(log_directory, log_level_custom, stem)


def _split_records(text: str) -> list[str]:
    """Split a log file's text into records (a record begins at a timestamped line)."""
    records: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if current and _RECORD_START.match(line):
            records.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        records.append("\n".join(current))
    return records


def read_log(
    base_directory: str | Path,
    *,
    file_stem: str | None = None,
    exceptions: bool = False,
) -> str:
    """Merge every writer's log under ``base_directory`` into one chronological string.

    Reads each writer's ``<base>/.logs/<writer>/<stem>.log`` (or ``.exception.log``), splits it
    into records, and sorts the records across all writers by their leading UTC timestamp. This
    reconstructs a single timeline from the per-writer files that concurrent writers produce.

    Args:
        base_directory: The study (or log) root whose ``.logs`` directory holds the writers.
        file_stem: The log file stem; defaults to ``"exporgo"``.
        exceptions: Merge the exception logs instead of the primary logs.

    Returns:
        The merged log text (empty if no matching log files exist).
    """
    logs_root = Path(base_directory) / _LOGS_DIRNAME
    stem = file_stem if file_stem is not None else "exporgo"
    suffix = f"{stem}.exception.log" if exceptions else f"{stem}.log"
    records: list[str] = []
    if logs_root.is_dir():
        for path in logs_root.glob(f"*/{suffix}"):
            records.extend(_split_records(path.read_text(encoding="utf-8")))
    records.sort()
    return "\n".join(records)


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
