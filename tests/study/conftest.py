"""Shared fixtures for the study tests.

Study logging attaches real loguru sinks (via ``init_logger``) to the process-global
logger; this fixture resets that global state around every test so sinks created by one
test never leak into another or keep pointing at a deleted temporary directory.
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
