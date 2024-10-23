from os import environ
from pathlib import Path

import numpy as np
import pytest

"""
CONFIGURATION FOR TESTING

"""

# MANUALLY MAKE TEMP DIRECTORY SINCE PYTEST'S TMP_PATH IS SOLELY FUNCTION SCOPE
_TEMPORARY_DIRECTORY = Path().cwd().joinpath("temp")
if not _TEMPORARY_DIRECTORY.exists():
    _TEMPORARY_DIRECTORY.mkdir(exist_ok=True)

@pytest.fixture(scope="session")
def temp_path():
    return _TEMPORARY_DIRECTORY
