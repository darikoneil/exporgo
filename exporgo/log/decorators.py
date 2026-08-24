"""Decorators that log a function's call, arguments, return value, and timing.

:func:`log_function_call` logs a call and its result at a single level;
:func:`log_major_function_call` additionally records wall-clock duration, intended
for pipeline-level entry points. Both use ``logger.opt(depth=1)`` and
:func:`functools.wraps` so log records are attributed to the caller and the wrapped
function's metadata is preserved.
"""

from __future__ import annotations

from functools import wraps
from time import time
from typing import TYPE_CHECKING

from loguru import logger

from .levels import LogLevel
from .rendering import _LOG_ELEMENT_LIMIT, render_object

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

__all__ = ["log_class", "log_function_call", "log_major_function_call"]


def _report_call(
    logger_: Any,
    func_name: str,
    level: LogLevel,
    *,
    args: tuple,
    kwargs: dict,
) -> None:
    """Log a decorated function's positional and keyword arguments."""
    rendered_args = [render_object(arg) for arg in args]
    rendered_kwargs = render_object(dict(kwargs))
    message = (
        f"Called '{func_name}' with values:\n\targs={rendered_args},"
        f"\n\tkwargs={rendered_kwargs}"
    )
    logger_.log(level.name, message)


def _report_return(
    logger_: Any,
    func_name: str,
    level: LogLevel,
    *,
    result: Any,
) -> None:
    """Log a decorated function's return value(s).

    Tuple results shorter than :data:`exporgo.log.rendering._LOG_ELEMENT_LIMIT` are
    logged one rendered element per line; all other results are logged as a single
    rendered value.
    """
    if isinstance(result, tuple) and len(result) < _LOG_ELEMENT_LIMIT:
        rendered = "\n".join(render_object(item) for item in result)
    else:
        rendered = render_object(result)
    message = f"Returned '{func_name}' with values:\n\t{rendered}"
    logger_.log(level.name, message)


def log_function_call(
    *, level: LogLevel = LogLevel.TRACE
) -> Callable[[Callable], Callable]:
    """Create a decorator that logs a function's arguments and return value.

    Lighter-weight than :func:`log_major_function_call`: logs the call and its
    result at a single level (no timing), for frequently-called helpers where
    per-call overhead and log volume should stay low.

    Args:
        level: Level at which both the call and return value are logged.

    Returns:
        A decorator that adds call/return logging while preserving the wrapped
        function's signature and metadata.
    """

    def wrapper(func: Callable) -> Callable:
        """Wrap ``func`` with single-level call/return logging."""
        name = func.__name__

        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            """Log the call, invoke the function, then log the return value."""
            logger_ = logger.opt(depth=1)
            _report_call(logger_, name, level, args=args, kwargs=kwargs)
            result = func(*args, **kwargs)
            _report_return(logger_, name, level, result=result)
            return result

        return wrapped

    return wrapper


def log_major_function_call(
    *,
    timing_level: LogLevel = LogLevel.INFO,
    args_level: LogLevel = LogLevel.DEBUG,
    rets_level: LogLevel = LogLevel.DEBUG,
) -> Callable[[Callable], Callable]:
    """Create a decorator that logs a function's call, timing, and return value.

    Intended for pipeline-level entry points where the call and its wall-clock
    duration are worth logging at a more visible level than the (typically more
    verbose) arguments and return values.

    Args:
        timing_level: Level for the "called"/"returned in N seconds" messages.
        args_level: Level at which the arguments are logged.
        rets_level: Level at which the return value is logged.

    Returns:
        A decorator that adds call/timing/return logging while preserving the
        wrapped function's signature and metadata.
    """

    def wrapper(func: Callable) -> Callable:
        """Wrap ``func`` with call/timing/return logging."""
        name = func.__name__

        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            """Log the timed call, invoke the function, then log timing and return."""
            logger_ = logger.opt(depth=1)
            start = time()

            logger_.log(timing_level.name, "Called '{}'", name)
            _report_call(logger_, name, args_level, args=args, kwargs=kwargs)

            result = func(*args, **kwargs)

            stop = time()
            logger_.log(timing_level.name, "'{}' returned in '{}' ", name, stop - start)
            _report_return(logger_, name, rets_level, result=result)

            return result

        return wrapped

    return wrapper


def log_class(parameters: object, level: LogLevel = LogLevel.DEBUG) -> None:
    """Log an object's class name and string representation.

    Useful for recording the resolved configuration of a parameters/config object
    (e.g. a dataclass or pydantic model) at the start of a pipeline stage.

    Args:
        parameters: Object to log; its ``str()`` representation is included, so it
            should be reasonably concise.
        level: Severity level at which to log.
    """
    message = f"{parameters.__class__.__name__}:\n{parameters}"
    logger.log(level.name, message)
