import sys
from dataclasses import dataclass
from itertools import product
from math import sin
from os import devnull
from pathlib import Path
from shutil import rmtree

import pytest

"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// CONSTANTS
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""

RAW_FILENAME = "raw.csv"


RESULTS_FILENAME = "results.csv"


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// ENCAPSULATIONS
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


@dataclass(frozen=True)
class ActionTestAttributes:
    raw_header: list[str]
    raw_data: list[list]
    raw_filename: str
    results_header: list[str]
    results_data: list[list]
    results_filename: str
    num_files_created: int
    num_files_in_files: int
    num_files_in_results: int


@dataclass(frozen=True)
class SourceTestAttributes:
    num_files_in_folder: int
    file_name: str
    file_contents: str
    num_folders_in_source: int
    folder_name: str
    num_files_total_in_source: int


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// SESSION FIXTURES
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


@pytest.fixture(scope="session")
def entry_point(request) -> str:
    """
    Get the entry point
    """
    return "exporgo"


@pytest.fixture(scope="session")
def simple_source_attributes(request) -> SourceTestAttributes:
    """
    Create dummy files for testing
    """
    return SourceTestAttributes(**{
        "num_files_in_folder": 3,
        "file_name": "dummy_file_*.txt",
        "file_contents": "dummy content *",
        "num_folders_in_source": 3,
        "folder_name": "dummy_folder_*",
        "num_files_total_in_source": 9,
    })


@pytest.fixture(scope="session", autouse=True)
def simple_action_attributes(request) -> ActionTestAttributes:
    """
    Create dummy files for testing
    """

    def make_result(x: float) -> list[float]:
        raw = sin(x)
        prepared = raw * -1 if raw < 0.0 else raw
        analyzed = raw * 2
        summarized = 1 if prepared > analyzed else -1
        return [x, raw, prepared, analyzed, summarized]

    data_length = 100
    raw_data = [[x, sin(x)] for x in range(data_length)]
    result_data = [make_result(x) for x in range(data_length)]

    return ActionTestAttributes(**{
    "raw_header":  ["Time (s)", "Raw Signal"],
    "raw_data": raw_data,
    "raw_filename": RAW_FILENAME,
    "results_header": ["Time (s)",
                       "Raw Signal",
                       "Prepared Signal",
                       "Analyzed Signal",
                       "Summarized Signal"],
    "results_data": result_data,
    "results_filename": RESULTS_FILENAME,
    "num_files_created": 2,
    "num_files_in_files": 1,
    "num_files_in_results": 1,
})


@pytest.fixture(scope="session", autouse=True)
def path_actions(request) -> Path:
    """
    Create dummy files for testing
    """

    return Path(request.config.rootpath).joinpath("tests").joinpath("behavior_driven_testing").joinpath("actions.py")


@pytest.fixture(scope="session", autouse=True)
def path_assets(request) -> Path:
    """
    Create dummy files for testing
    """
    return Path(request.config.rootpath).joinpath("tests").joinpath("assets")


@pytest.fixture(scope="session", autouse=True)
def suppress_tqdm():
    """
    Suppress tqdm output
    """
    from functools import partialmethod

    from tqdm import tqdm

    # noinspection PyTypeChecker
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// FUNCTION FIXTURES
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


@pytest.fixture(scope="function")
def simple_source(request, tmp_path, simple_source_attributes) -> Path:
    """
    Create dummy files for testing
    """
    def name_file(file_: int) -> str:
        return simple_source_attributes.file_name.replace("*", str(file_))

    def name_content(file_: int) -> str:
        return simple_source_attributes.file_contents.replace("*", str(file_))

    def name_folder(folder_: int) -> str:
        return simple_source_attributes.folder_name.replace("*", str(folder_))

    source = tmp_path.joinpath("source")
    source.mkdir(exist_ok=True, parents=True)

    for file, folder in product(range(simple_source_attributes.num_files_in_folder),
                                range(simple_source_attributes.num_folders_in_source)):
        dummy_folder = source.joinpath(name_folder(folder))
        dummy_folder.mkdir(exist_ok=True, parents=True)
        dummy_file = dummy_folder.joinpath(name_file(file))
        dummy_file.write_text(name_content(file))

    def cleanup():
        rmtree(source)

    request.addfinalizer(cleanup)

    return source


@pytest.fixture(scope="function")
def destination(request, tmp_path) -> Path:
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
def path_steps(request, tmp_path) -> Path:
    """
    Create dummy files for testing
    """

    return tmp_path.joinpath("registered_steps.json")


@pytest.fixture(scope="function")
def path_experiments(request, tmp_path) -> Path:
    """
    Create dummy files for testing
    """

    return tmp_path.joinpath("registered_experiments.json")


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// HELPERS
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


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
