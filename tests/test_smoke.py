"""Smoke tests confirming the package imports and exposes its version."""

import exporgo


def test_package_imports() -> None:
    assert exporgo is not None


def test_version_is_exposed() -> None:
    assert isinstance(exporgo.__version__, str)
    assert exporgo.__version__
