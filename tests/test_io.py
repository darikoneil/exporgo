# noinspection PyUnresolvedReferences
from itertools import product
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from joblib import parallel_config

# noinspection PyProtectedMember
# noinspection PyProtectedMember
from exporgo._io import select_directory, select_file, verbose_copy


@patch('exporgo._io.askopenfilename', return_value=Path.cwd().joinpath("tests").joinpath("test_io.py"))
@patch('exporgo._io.Tk')
def test_select_file_returns_correct_path(mock_tk, mock_askopenfilename):
    result = select_file()
    assert result == Path.cwd().joinpath("file.txt")
    mock_tk.return_value.destroy.assert_called_once()

@patch('exporgo._io.askopenfilename', return_value='.')
@patch('exporgo._io.Tk')
def test_select_file_raises_file_not_found_error(mock_tk, mock_askopenfilename):
    with pytest.raises(FileNotFoundError):
        select_file()
    mock_tk.return_value.destroy.assert_called_once()


@patch('exporgo._io.askdirectory', return_value=Path.cwd().joinpath("tests"))
@patch('exporgo._io.Tk')
def test_directory_selection_returns_correct_path(mock_tk, mock_askdirectory):
    result = select_directory()
    assert result == Path.cwd().joinpath("folder")
    mock_tk.return_value.destroy.assert_called_once()


@patch('exporgo._io.askdirectory', return_value=".")
@patch('exporgo._io.Tk')
def test_directory_selection_raises_io_error(mock_tk, mock_askdirectory):
    with pytest.raises(FileNotFoundError):
        select_directory()
    mock_tk.return_value.destroy.assert_called_once()


def test_verbose_copy(source, destination):
    with parallel_config(n_jobs=1):
        verbose_copy(source, destination)

    source_files = list(source.rglob("*"))
    destination_files = list(destination.rglob("*"))
    assert len(source_files) == len(destination_files)
