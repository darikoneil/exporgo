from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from joblib import parallel_config

# noinspection PyProtectedMember
from exporgo.io import (import_callable_from_file, import_function_from_file,
                        select_directory, select_file, verbose_copy)


# noinspection PyUnusedLocal
@patch('exporgo.io.askopenfilename', return_value=__file__)
@patch('exporgo.io.Tk')
def test_select_file_returns_correct_path(mock_tk, mock_askopenfilename):
    # Mock the Tk() class and the askopenfilename function
    result = select_file()
    assert result == Path(__file__)
    mock_tk.return_value.destroy.assert_called_once()


# noinspection PyUnusedLocal
@patch('exporgo.io.askopenfilename', return_value=".")
@patch('exporgo.io.Tk')
def test_select_file_raises_file_not_found_error(mock_tk, mock_askopenfilename):
    with pytest.raises(FileNotFoundError):
        select_file()
    mock_tk.return_value.destroy.assert_called_once()


# noinspection PyUnusedLocal
@patch('exporgo.io.askdirectory', return_value=Path.cwd())
@patch('exporgo.io.Tk')
def test_directory_selection_returns_correct_path(mock_tk, mock_askdirectory):
    result = select_directory()
    assert result == Path.cwd()
    mock_tk.return_value.destroy.assert_called_once()


# noinspection PyUnusedLocal
@patch('exporgo.io.askdirectory', return_value=".")
@patch('exporgo.io.Tk')
def test_directory_selection_raises_file_not_found_error(mock_tk, mock_askdirectory):
    with pytest.raises(FileNotFoundError):
        select_directory()
    mock_tk.return_value.destroy.assert_called_once()


def test_verbose_copy(simple_source, destination):
    with parallel_config(n_jobs=1):
        verbose_copy(simple_source, destination)

    source_files = list(simple_source.rglob("*"))
    destination_files = list(destination.rglob("*"))
    assert len(source_files) == len(destination_files)


def test_callable_imported_successfully():
        with patch('exporgo.io.spec_from_file_location') as mock_spec, \
             patch('exporgo.io.module_from_spec') as mock_module, \
             patch('exporgo.io.modules') as mock_modules:
            mock_loader = MagicMock()
            mock_spec.return_value.loader = mock_loader
            mock_module.return_value.some_callable = lambda: "test"
            mock_modules.__setitem__.return_value = None

            result = import_callable_from_file('some_callable', 'some_module', 'some_path')
            assert result() == "test"


def test_function_imported_successfully():
    with patch('exporgo.io.spec_from_file_location') as mock_spec, \
         patch('exporgo.io.module_from_spec') as mock_module:
        mock_loader = MagicMock()
        mock_spec.return_value.loader = mock_loader
        mock_module.return_value.some_function = lambda: "test"
        mock_loader.exec_module.return_value = None

        result = import_function_from_file('some_function', Path('some_path'))
        assert result() == "test"
