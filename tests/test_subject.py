from unittest.mock import patch

import pytest
from joblib import parallel_config

# noinspection PyUnresolvedReferences,PyProtectedMember
from exporgo._io import verbose_copy
from exporgo.exceptions import MissingFilesError
from exporgo.subject import Subject
from exporgo.types import Priority
from tests.conftest import BlockPrinting


class TestSubject:

    def test_subject_initialization_with_valid_data(self, tmp_path):
        with patch("exporgo.subject.IPythonLogger.start") as mock_ipythonlogger:
            subject = Subject(name="source",
                              directory=tmp_path,
                              study="Study1",
                              meta = {"test": "details"},
                              priority=Priority.HIGH,
                              extra = "extra details")
            assert subject.name == "source"
            assert subject.directory == tmp_path.joinpath("source")
            assert subject.study == "Study1"
            assert subject.priority == Priority.HIGH
            assert subject.meta == {"test": "details", "extra": "extra details"}
            subject.index()
            assert mock_ipythonlogger.start_log.called_once()

    def test_subject_initialization_without_directory(self, tmp_path):
        with patch("exporgo.subject.select_directory") as mock_select_directory:
            with patch("exporgo.subject.IPythonLogger.start") as mock_ipythonlogger:
                mock_select_directory.return_value = tmp_path
                subject = Subject(name="TestSubject")
                assert subject.directory == tmp_path.joinpath("TestSubject")
                assert mock_ipythonlogger.start_log.called_once()

    def test_subject_print(self, tmp_path):
        with patch("exporgo.subject.IPythonLogger.start") as mock_ipythonlogger:
            subject = Subject(name="TestSubject",
                              directory=tmp_path,
                              study="Study1",
                              meta = {"test": "details"},
                              priority=Priority.HIGH,
                              extra = "extra details")
            with BlockPrinting():
                print(subject)
            assert mock_ipythonlogger.start_log.called_once()

    @pytest.mark.skip("Being refactored")
    def test_subject_indirect_get_experiment(self, tmp_path):
        with patch("exporgo.subject.IPythonLogger.start") as mock_ipythonlogger:
            subject = Subject(name="TestSubject",
                              directory=tmp_path,
                              study="Study1",
                              meta = {"test": "details"},
                              extra = "extra details")
            subject.experiments["MockExperiment"] = "MockExperiment_"
            assert getattr(subject, "MockExperiment") == "MockExperiment_"
            assert subject.get("MockExperiment") == "MockExperiment_"
            assert mock_ipythonlogger.start_log.called_once()

    @pytest.mark.skip("Being refactored")
    def test_subject_create_experiment(self, tmp_path):
        with patch("exporgo.subject.IPythonLogger.start") as mock_ipythonlogger:
            subject = Subject(name="TestSubject",
                              directory=tmp_path,
                              study="Study1",
                              meta = {"test": "details"},
                              extra = "extra details")
            subject.create_experiment("MockExperiment", "GenericExperiment")
            assert "MockExperiment" in subject.experiments
            assert mock_ipythonlogger.start_log.called_once()

    @pytest.mark.skip("Being refactored")
    def test_subject_save_load(self, tmp_path, source):
        # noinspection PyUnusedLocal
        with patch("exporgo.subject.IPythonLogger") as mock_ipythonlogger:
            subject = Subject(name="TestSubject",
                              directory=tmp_path,
                              study="Study1",
                              meta = {"test": "details"},
                              extra = "extra details")
            subject.create_experiment("MockExperiment", "GenericExperiment")
            with parallel_config(n_jobs=1):
                verbose_copy(source, subject.get("MockExperiment").get("data").directory)
            subject.get("MockExperiment").index()
            subject.save()
            subject.logger.end()
            subject_copy = Subject.load(tmp_path.joinpath("TestSubject"))
            assert subject_copy.name == "TestSubject"
            assert subject_copy.study == "Study1"
            assert subject_copy.meta == {"test": "details", "extra": "extra details"}
            assert "MockExperiment" in subject_copy.contains
            assert subject_copy.get("MockExperiment").file_tree.num_files == 9

    @pytest.mark.skip("Being refactored")
    def test_subject_validate(self, tmp_path):
        with patch("exporgo.subject.IPythonLogger.start") as mock_ipythonlogger:
            subject = Subject(name="TestSubject",
                              directory=tmp_path,
                              study="Study1",
                              meta = {"test": "details"},
                              extra = "extra details")
            subject.create_experiment("MockExperiment", "GenericExperiment")
            subject.validate()
            assert mock_ipythonlogger.start_log.called_once()

    @pytest.mark.skip("Being refactored")
    def test_subject_validate_fail(self, tmp_path, source):
        with patch("exporgo.subject.IPythonLogger.start") as mock_ipythonlogger:
            subject = Subject(name="TestSubject",
                              directory=tmp_path,
                              study="Study1",
                              meta = {"test": "details"},
                              )
            subject.create_experiment("MockExperiment", "GenericExperiment")
            with parallel_config(n_jobs=1):
                verbose_copy(source, subject.get("MockExperiment").get("data").directory)
            subject.get("MockExperiment").index()
            list(subject.get("MockExperiment").get("data").files.values())[0].unlink()

            with pytest.raises(MissingFilesError):
                subject.validate()
            assert mock_ipythonlogger.start_log.called_once()
