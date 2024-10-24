# noinspection PyUnresolvedReferences
from itertools import product

import pytest
from joblib import parallel_config

# noinspection PyProtectedMember
from exporgo._io import verbose_copy


def test_verbose_copy(source, destination):
    with parallel_config(n_jobs=1):
        verbose_copy(source, destination)

    source_files = list(source.rglob("*"))
    destination_files = list(destination.rglob("*"))
    assert len(source_files) == len(destination_files)
