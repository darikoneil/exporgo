import sys
from itertools import product
from os import devnull
from shutil import rmtree

import pytest

"""
CONFIGURATION FOR TESTING
"""


@pytest.fixture(scope="function")
def source(request, tmp_path):
    """
    Create dummy files for testing
    """
    source = tmp_path.joinpath("source")
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
def destination(request, tmp_path):
    """
    Create dummy files for testing
    """

    destination = tmp_path.joinpath("destination")
    destination.mkdir(exist_ok=True, parents=True)

    def cleanup():
        rmtree(destination)

    request.addfinalizer(cleanup)

    return destination


@pytest.fixture(scope="function")
def path_steps(request, tmp_path):
    """
    Create dummy files for testing
    """

    return tmp_path.joinpath("registered_steps.json")


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