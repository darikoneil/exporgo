import sys
from os import devnull
from pathlib import Path

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


# Simple class that blocks printing
class BlockPrinting:
    """
    Simple context manager that blocks printing
    """
    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = open(devnull, "w")

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._stdout