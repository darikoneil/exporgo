# noinspection PyUnresolvedReferences
from itertools import product
from shutil import rmtree

import pytest
from joblib import parallel_config

# noinspection PyProtectedMember
from exporgo._io import verbose_copy
from tests.conftest import BlockPrinting


def test_verbose_copy(temp_path):
    # Create nested dummy files & folders, verbose copy, then check if the files are copied, then delete
    source = temp_path.joinpath("source")
    source.mkdir(exist_ok=True, parents=True)
    destination = temp_path.joinpath("destination")
    destination.mkdir(exist_ok=True, parents=True)

    for file, folder in product(range(3), range(3)):
        dummy_folder = source.joinpath(f"dummy_folder_{folder}")
        dummy_folder.mkdir(exist_ok=True, parents=True)
        dummy_file = dummy_folder.joinpath(f"dummy_file_{file}.txt")
        dummy_file.write_text(f"dummy content {file}")

    with parallel_config(n_jobs=1):
        verbose_copy(source, destination)

    source_files = list(source.rglob("*"))
    destination_files = list(destination.rglob("*"))
    assert len(source_files) == len(destination_files)

    rmtree(source)
    rmtree(destination)
