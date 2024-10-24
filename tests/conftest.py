import sys
from itertools import product
from os import devnull
from pathlib import Path
from shutil import rmtree

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


@pytest.fixture(scope="function")
def source(request):
    """
    Create dummy files for testing
    """

    source = _TEMPORARY_DIRECTORY.joinpath("source")
    source.mkdir(exist_ok=True, parents=True)

    for file, folder in product(range(3), range(3)):
        dummy_folder = source.joinpath(f"dummy_folder_{folder}")
        dummy_folder.mkdir(exist_ok=True, parents=True)
        dummy_file = dummy_folder.joinpath(f"dummy_file_{file}.txt")
        dummy_file.write_text(f"dummy content {file}")

    def cleanup():
        rmtree(source)

    request.addfinalizer(cleanup)

    return source


@pytest.fixture(scope="function")
def destination(request):
    """
    Create dummy files for testing
    """

    destination = _TEMPORARY_DIRECTORY.joinpath("destination")
    destination.mkdir(exist_ok=True, parents=True)

    def cleanup():
        rmtree(destination)

    request.addfinalizer(cleanup)

    return destination


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