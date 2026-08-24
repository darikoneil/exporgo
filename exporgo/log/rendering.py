"""Render arbitrary objects into compact, log-friendly strings.

:func:`render_object` uses :func:`functools.singledispatch` so large or unwieldy
values are summarized rather than dumped verbatim into a log record. Handlers for
:class:`numpy.ndarray` and :class:`polars.DataFrame` are registered only when those
libraries are importable, so this module (and exporgo's base install) depend on
neither; absent them, such objects fall back to :func:`str`.
"""

from functools import singledispatch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import polars as pl

__all__ = ["render_object"]


_LOG_ELEMENT_LIMIT: int = 10
"""Maximum number of sequence elements rendered when logging a collection."""

_LOG_COLUMN_LIMIT: int = 5
"""Maximum number of :class:`polars.DataFrame` columns rendered in log output."""


@singledispatch
def render_object(obj: object) -> str:
    """Render an arbitrary object as a log-friendly string (fallback: ``str``).

    Dispatches on ``obj``'s type; collections, mappings, and (when available)
    numpy arrays and polars DataFrames have specialized, size-limited renderings
    registered below to keep log records readable.

    Args:
        obj: Object to render.

    Returns:
        A string representation of ``obj`` suitable for a log message.
    """
    return str(obj)


def _render_collection(obj: tuple | list | set) -> str:
    """Render a collection's length and a bounded sample of its elements."""
    num_elements = len(obj)
    sample = list(obj)[:_LOG_ELEMENT_LIMIT]
    return f"{obj.__class__.__name__} of length {num_elements}:\n\t{sample}"


@render_object.register(tuple)
@render_object.register(list)
@render_object.register(set)
def _render_object_collection(obj: tuple | list | set) -> str:
    """Render a tuple, list, or set as a length-prefixed, bounded sample."""
    return _render_collection(obj)


@render_object.register(dict)
def _render_object_dict(obj: dict) -> str:
    """Recursively render each mapping value via :func:`render_object`."""
    return str({key: render_object(value) for key, value in obj.items()})


def _register_optional_renderers() -> None:
    """Register numpy/polars renderers when those libraries are importable.

    Keeping the imports inside this function (called once at import time) means
    the module never hard-depends on numpy or polars; if either is missing, its
    renderer is simply not registered and those objects fall back to ``str``.
    """
    try:
        import numpy as np
    except ImportError:
        pass
    else:

        @render_object.register(np.ndarray)
        def _render_object_numpy(obj: "np.ndarray") -> str:
            """Summarize a numpy array by shape and dtype rather than contents."""
            return f"Numpy array of shape {obj.shape} and dtype {obj.dtype!s}"

    try:
        import polars as pl
    except ImportError:
        pass
    else:

        @render_object.register(pl.DataFrame)
        def _render_object_polars(obj: "pl.DataFrame") -> str:
            """Render a polars DataFrame as a bounded, dtype-free ASCII table."""
            with pl.Config() as cfg:
                cfg.set_ascii_tables(True)
                cfg.set_tbl_rows(_LOG_ELEMENT_LIMIT)
                cfg.set_tbl_cols(_LOG_COLUMN_LIMIT)
                cfg.set_tbl_hide_column_data_types(True)
                cfg.set_tbl_dataframe_shape_below(True)
                return str(obj)


_register_optional_renderers()
