"""Shared fixtures for the datastore tests.

Store writes emit loguru records and, when a store is exercised through a saved study,
real sinks are attached to the process-global logger; this fixture resets that global
state around every test so sinks or the enabled/disabled flag never leak between tests.
"""

from collections.abc import Iterator

import pytest
from loguru import logger


@pytest.fixture(autouse=True)
def reset_loguru() -> Iterator[None]:
    """Clear all loguru sinks and re-silence exporgo before and after each test."""
    logger.remove()
    logger.disable("exporgo")
    yield
    logger.remove()
    logger.disable("exporgo")
