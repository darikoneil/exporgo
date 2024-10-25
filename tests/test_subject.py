from turtledemo.sorting_animate import Block
from unittest.mock import patch

from exporgo.subject import Subject
from tests.conftest import BlockPrinting


class TestSubject:

    def test_subject_initialization_with_valid_data(self, tmp_path):
        with patch("exporgo.subject.IPythonLogger.start_log") as mock_ipythonlogger:
            subject = Subject(name="source",
                              directory=tmp_path,
                              species="Mouse",
                              study="Study1",
                              condition="Control",
                              meta = {"test": "details"},
                              extra = "extra details")
            assert subject.name == "source"
            assert subject.directory == tmp_path.joinpath("source")
            assert subject.species == "Mouse"
            assert subject.study == "Study1"
            assert subject.condition == "Control"
            assert subject.meta == {"test": "details", "extra": "extra details"}
            subject.index()
            assert mock_ipythonlogger.start_log.called_once()

    def test_subject_initialization_without_directory(self, tmp_path):
        with patch("exporgo.subject.select_directory") as mock_select_directory:
            with patch("exporgo.subject.IPythonLogger.start_log") as mock_ipythonlogger:
                mock_select_directory.return_value = tmp_path
                subject = Subject(name="TestSubject")
                assert subject.directory == tmp_path.joinpath("TestSubject")
                assert mock_ipythonlogger.start_log.called_once()

    def test_subject_print(self, tmp_path):
        with patch("exporgo.subject.IPythonLogger.start_log") as mock_ipythonlogger:
            subject = Subject(name="TestSubject",
                              directory=tmp_path,
                              species="Mouse",
                              study="Study1",
                              condition="Control",
                              meta = {"test": "details"},
                              extra = "extra details")
            with BlockPrinting():
                print(subject)
            assert mock_ipythonlogger.start_log.called_once()

    def test_subject_indirect_get_experiment(self, tmp_path):
        with patch("exporgo.subject.IPythonLogger.start_log") as mock_ipythonlogger:
            subject = Subject(name="TestSubject",
                              directory=tmp_path,
                              species="Mouse",
                              study="Study1",
                              condition="Control",
                              meta = {"test": "details"},
                              extra = "extra details")
            subject._experiments["MockExperiment"] = "MockExperiment_"
            assert getattr(subject, "MockExperiment") == "MockExperiment_"
            assert subject.get("MockExperiment") == "MockExperiment_"
            assert mock_ipythonlogger.start_log.called_once()

    def test_subject_create_experiment(self, tmp_path):
        with patch("exporgo.subject.IPythonLogger.start_log") as mock_ipythonlogger:
            subject = Subject(name="TestSubject",
                              directory=tmp_path,
                              species="Mouse",
                              study="Study1",
                              condition="Control",
                              meta = {"test": "details"},
                              extra = "extra details")
            subject.create_experiment("MockExperiment", "GenericExperiment")
            assert "MockExperiment" in subject._experiments
            assert mock_ipythonlogger.start_log.called_once()