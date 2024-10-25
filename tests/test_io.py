from pathlib import Path
from unittest.mock import patch

import pytest
from joblib import parallel_config

# noinspection PyProtectedMember
from exporgo._io import select_directory, select_file, verbose_copy


# noinspection PyUnusedLocal
@patch('exporgo._io.askopenfilename', return_value=__file__)
@patch('exporgo._io.Tk')
def test_select_file_returns_correct_path(mock_tk, mock_askopenfilename):
    # Mock the Tk() class and the askopenfilename function
    result = select_file()
    assert result == Path(__file__)
    mock_tk.return_value.destroy.assert_called_once()


# noinspection PyUnusedLocal
@patch('exporgo._io.askopenfilename', return_value=".")
@patch('exporgo._io.Tk')
def test_select_file_raises_file_not_found_error(mock_tk, mock_askopenfilename):
    with pytest.raises(FileNotFoundError):
        select_file()
    mock_tk.return_value.destroy.assert_called_once()


# noinspection PyUnusedLocal
@patch('exporgo._io.askdirectory', return_value=Path.cwd())
@patch('exporgo._io.Tk')
def test_directory_selection_returns_correct_path(mock_tk, mock_askdirectory):
    result = select_directory()
    assert result == Path.cwd()
    mock_tk.return_value.destroy.assert_called_once()


# noinspection PyUnusedLocal
@patch('exporgo._io.askdirectory', return_value=".")
@patch('exporgo._io.Tk')
def test_directory_selection_raises_file_not_found_error(mock_tk, mock_askdirectory):
    with pytest.raises(FileNotFoundError):
        select_directory()
    mock_tk.return_value.destroy.assert_called_once()


def test_verbose_copy(source, destination):
    with parallel_config(n_jobs=1):
        verbose_copy(source, destination)

    source_files = list(source.rglob("*"))
    destination_files = list(destination.rglob("*"))
    assert len(source_files) == len(destination_files)
