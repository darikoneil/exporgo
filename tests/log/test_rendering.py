"""Tests for compact, log-friendly object rendering."""

import numpy as np
import polars as pl
import pytest

from exporgo.log.rendering import render_object


def test_fallback_rendering_uses_str() -> None:
    class _Value:
        def __str__(self) -> str:
            return "rendered-value"

    assert render_object(_Value()) == "rendered-value"


def test_numpy_rendering_reports_shape_and_dtype() -> None:
    rendered = render_object(np.zeros((2, 3), dtype=np.float32))

    assert rendered == "Numpy array of shape (2, 3) and dtype float32"


def test_polars_rendering_is_bounded() -> None:
    dataframe = pl.DataFrame({f"column_{column}": range(20) for column in range(8)})

    rendered = render_object(dataframe)

    assert isinstance(rendered, str)
    assert "(20, 8)" in rendered
    assert "column_0" in rendered
    assert len(rendered.splitlines()) < 30


@pytest.mark.parametrize(
    ("value", "collection_name"),
    [
        ((1, 2, 3), "tuple"),
        ([1, 2, 3], "list"),
        ({1, 2, 3}, "set"),
    ],
)
def test_collection_rendering_is_text(
    value: tuple[int, ...] | list[int] | set[int],
    collection_name: str,
) -> None:
    rendered = render_object(value)

    assert isinstance(rendered, str)
    assert rendered.startswith(f"{collection_name} of length 3:")


def test_collection_rendering_is_bounded() -> None:
    rendered = render_object(list(range(20)))

    assert "list of length 20:" in rendered
    assert str(list(range(10))) in rendered
    assert "19" not in rendered


def test_dictionary_rendering_recurses_into_values() -> None:
    rendered = render_object({"samples": set(range(3))})

    assert isinstance(rendered, str)
    assert "set of length 3:" in rendered
