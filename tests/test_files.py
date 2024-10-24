import pytest

from exporgo.files import FileMap


def test_file_map(source):
    file_map = FileMap()
    for file in source.rglob("*"):
        file_map.update({file.name: file})
