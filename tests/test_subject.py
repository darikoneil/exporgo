from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from exporgo.subject import MissingFilesError, Subject


@patch('exporgo.subject.IPythonLogger')
@patch('exporgo.subject.ModificationLogger')
def subject_initialization_creates_directory(mock_mod_logger, mock_ipy_logger):
    mock_directory = MagicMock(spec=Path)
    mock_directory.name = "TestSubject"
    mock_directory.exists.return_value = False
    subject = Subject(name="TestSubject", directory=mock_directory)
    mock_directory.joinpath.assert_called_with("TestSubject")
    mock_directory.mkdir.assert_called_once()

@patch('exporgo.subject.IPythonLogger')
@patch('exporgo.subject.ModificationLogger')
def subject_initialization_uses_existing_directory(mock_mod_logger, mock_ipy_logger):
    mock_directory = MagicMock(spec=Path)
    mock_directory.name = "TestSubject"
    mock_directory.exists.return_value = True
    subject = Subject(name="TestSubject", directory=mock_directory)
    mock_directory.joinpath.assert_not_called()
    mock_directory.mkdir.assert_not_called()

@patch('exporgo.subject.IPythonLogger')
@patch('exporgo.subject.ModificationLogger')
def subject_str_representation(mock_mod_logger, mock_ipy_logger):
    subject = Subject(name="TestSubject")
    result = str(subject)
    assert "Mouse: TestSubject" in result
    assert "Instantiated: " in result

@patch('exporgo.subject.IPythonLogger')
@patch('exporgo.subject.ModificationLogger')
def subject_save_creates_organization_file(mock_mod_logger, mock_ipy_logger):
    subject = Subject(name="TestSubject")
    with patch('builtins.open', MagicMock()) as mock_open:
        subject.save()
        mock_open.assert_called_with(subject.organization_file, "w")

@patch('exporgo.subject.IPythonLogger')
@patch('exporgo.subject.ModificationLogger')
def subject_loads_correctly(mock_mod_logger, mock_ipy_logger):
    mock_directory = MagicMock(spec=Path)
    mock_directory.joinpath.return_value = Path("organization_file.json")
    with patch('builtins.open', MagicMock()), patch('exporgo.subject.load', return_value=Subject()):
        subject = Subject.load(mock_directory)
        assert isinstance(subject, Subject)

@patch('exporgo.subject.IPythonLogger')
@patch('exporgo.subject.ModificationLogger')
def subject_creates_experiment(mock_mod_logger, mock_ipy_logger):
    subject = Subject(name="TestSubject")
    mock_experiment = MagicMock()
    subject.create_experiment(name="TestExperiment", mix_ins=[mock_experiment])
    assert hasattr(subject, "TestExperiment")

@patch('exporgo.subject.IPythonLogger')
@patch('exporgo.subject.ModificationLogger')
def subject_records_modifications(mock_mod_logger, mock_ipy_logger):
    subject = Subject(name="TestSubject")
    subject.record("Test modification")
    assert subject.modifications[0][0] == "Test modification"

@patch('exporgo.subject.IPythonLogger')
@patch('exporgo.subject.ModificationLogger')
def subject_validates_experiments(mock_mod_logger, mock_ipy_logger):
    subject = Subject(name="TestSubject")
    mock_experiment = MagicMock()
    subject.create_experiment(name="TestExperiment", mix_ins=[mock_experiment])
    subject.validate()
    mock_experiment.validate.assert_called_once()

@patch('exporgo.subject.IPythonLogger')
@patch('exporgo.subject.ModificationLogger')
def subject_raises_missing_files_error(mock_mod_logger, mock_ipy_logger):
    subject = Subject(name="TestSubject")
    mock_experiment = MagicMock()
    mock_experiment.validate.side_effect = MissingFilesError(missing_files={"file1": "missing"})
    subject.create_experiment(name="TestExperiment", mix_ins=[mock_experiment])
    with pytest.raises(MissingFilesError):
        subject.validate()