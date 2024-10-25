from exporgo.subject import Subject
from unittest.mock import patch

class TestSubject:

    def test_subject_initialization_with_valid_data(self, tmp_path):
        with patch("exporgo.subject.IPythonLogger.start_log") as mock_ipythonlogger:
            subject = Subject(name="TestSubject",
                              directory=tmp_path,
                              species="Mouse",
                              study="Study1",
                              condition="Control",
                              meta = {"test": "details"},
                              extra = "extra details")
            assert subject.name == "TestSubject"
            assert subject.directory == tmp_path.joinpath("TestSubject")
            assert subject.species == "Mouse"
            assert subject.study == "Study1"
            assert subject.condition == "Control"
            assert subject.meta == {"test": "details", "extra": "extra details"}
            assert mock_ipythonlogger.start_log.called_once()

    def test_subject_initialization_without_directory(self, tmp_path):
        with patch("exporgo.subject.select_directory") as mock_select_directory:
            with patch("exporgo.subject.IPythonLogger.start_log") as mock_ipythonlogger:
                mock_select_directory.return_value = tmp_path
                subject = Subject(name="TestSubject")
                assert subject.directory == tmp_path.joinpath("TestSubject")
                assert mock_ipythonlogger.start_log.called_once()
