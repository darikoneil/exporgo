from unittest.mock import MagicMock, patch

import pytest
from joblib import parallel_config
from pydantic import ValidationError

# noinspection PyProtectedMember
from exporgo._logging import IPythonLogger
# noinspection PyProtectedMember
from exporgo._version import __current_version__
from exporgo.exceptions import MissingFilesError
# noinspection PyUnresolvedReferences,PyProtectedMember
from exporgo.io import verbose_copy
from exporgo.organization.experiment import Experiment, ExperimentRegistry
from exporgo.organization.step import StepRegistry
from exporgo.organization.subject import Subject, ValidSubject
from exporgo.registry import PATH_EXPERIMENTS, PATH_STEPS
from exporgo.types import Priority, Status
from tests.conftest import BlockPrinting


class TestValidSubject:
    test_name = "TestSubject"
    test_base_directory = None
    test_directory = None
    test_study = "TestStudy"
    test_priority = Priority.CRITICAL
    test_status = Status.SOURCE
    test_meta = {"test": "details"}
    test_file_sets = "files"
    test_version = __current_version__
    test_experiments = None

    @pytest.fixture(scope="function", autouse=True)
    def setup_class(self, tmp_path):
        self.test_base_directory = tmp_path
        self.test_directory = tmp_path.joinpath(self.test_name)

    def test_serialization_directory(self):
        serialized_directory = ValidSubject.serialize_directory(self.test_directory)
        assert serialized_directory == str(self.test_directory)

    def test_serialization_experiments(self):
        experiment = MagicMock(spec=Experiment)
        self.test_experiments = {"Mock Experiment": experiment}
        _ = ValidSubject.serialize_experiments(self.test_experiments)
        assert experiment.__serialize__.called

    def test_serialization_priority(self):
        serialized_priority = ValidSubject.serialize_priority(self.test_priority)
        assert serialized_priority == Priority.__serialize__(self.test_priority)

    def test_serialization_status(self):
        serialized_status = ValidSubject.serialize_status(self.test_status)
        assert serialized_status == Status.__serialize__(self.test_status)

    def test_validate_experiments(self):
        experiment = MagicMock(spec=Experiment)
        self.test_experiments = {"Mock Experiment": experiment}
        with pytest.raises(ValidationError): # we want to check for assertion, don't care about validation error
            ValidSubject.validate_experiments({"Mock Experiment": {"key": "value"}})
            assert experiment.__deserialize__.called

    def test_validate_priority(self):
        validated_priority = ValidSubject.validate_priority(self.test_priority.__serialize__())
        assert validated_priority == self.test_priority

    def test_validate_status(self):
        validated_status = ValidSubject.validate_status(self.test_status.__serialize__())
        assert validated_status == self.test_status

    def test_validate_version(self):
        validated_version = ValidSubject.validate_version(self.test_version)
        assert validated_version == self.test_version


class TestSubject:
    test_name = "source"
    test_base_directory = None
    test_directory = None
    test_study = "TestStudy"
    test_meta = {"test": "details"}
    test_priority = Priority.HIGH
    test_extra = "extra details"
    test_subject = None

    @pytest.fixture(scope="function", autouse=True)
    def setup_class(self, tmp_path):
        self.test_base_directory = tmp_path
        self.test_directory = tmp_path.joinpath(self.test_name)
        self.test_directory.mkdir()
        ExperimentRegistry._ExperimentRegistry__path = PATH_EXPERIMENTS
        StepRegistry._StepRegistry__path = PATH_STEPS

    @pytest.fixture(scope="function", autouse=True)
    def setup_subject(self):
        self.mock_logger = MagicMock(spec=IPythonLogger)
        self.test_subject = Subject(name=self.test_name,
                                    directory=self.test_base_directory,
                                    study=self.test_study,
                                    meta=self.test_meta,
                                    priority=self.test_priority,
                                    extra=self.test_extra)

    def test_subject_valid_initialization(self):
        assert self.test_subject.name == self.test_name
        assert self.test_subject.directory == self.test_directory
        assert self.test_subject.study == self.test_study
        assert self.test_subject.meta == {**self.test_meta, **{"extra": self.test_extra}}
        assert self.test_subject.priority == self.test_priority
        assert self.test_subject.version == __current_version__

    def test_subject_initialization_without_directory(self):
        with (patch("exporgo.organization.subject.select_directory", return_value=self.test_base_directory)
              as mock_select_directory):
            subject = Subject(name=self.test_name,
                              study=self.test_study,
                              meta=self.test_meta,
                              priority=self.test_priority,
                              extra=self.test_extra)
            assert mock_select_directory.called_once()
            assert subject.directory == self.test_base_directory.joinpath(self.test_name)

    def test_subject_print(self):
        with BlockPrinting():
            print(self.test_subject)
        with BlockPrinting():
            self.test_subject.meta = {}

    def test_subject_indirect_get_experiment(self):
        self.test_subject.experiments["Mock Experiment"] = MagicMock(spec=Experiment)
        assert getattr(self.test_subject, "Mock Experiment") == self.test_subject.experiments.get("Mock Experiment")
        assert self.test_subject.get("Mock Experiment") == self.test_subject.experiments.get("Mock Experiment")

    def test_subject_create_experiment(self):
        self.test_subject.create_experiment("Mock Experiment", "generic_experiment")
        assert "Mock Experiment" in self.test_subject.experiments
        with BlockPrinting():
            print(self.test_subject)

    def test_subject_save_load(self, simple_source):
        # dependent on test_subject_create_experiment :/
        self.test_subject.create_experiment("Mock Experiment", "generic_experiment")
        with parallel_config(n_jobs=1):
            verbose_copy(simple_source, self.test_subject.get("Mock Experiment").get("files").directory)
        self.test_subject.get("Mock Experiment").index()
        self.test_subject.save()
        self.test_subject.logger.end()

        subject_copy = Subject.load(self.test_subject.directory.joinpath("organization.yaml"))
        subject_copy.validate()
        for key, attr in vars(self.test_subject).items():
            if key in ["logger", "modifications", "_modifications"]:
                continue
            else:
                assert getattr(subject_copy, key) == attr

    def test_subject_failed_validation(self, simple_source):
        self.test_subject.create_experiment("Mock Experiment", "generic_experiment")
        with parallel_config(n_jobs=1):
            verbose_copy(simple_source, self.test_subject.get("Mock Experiment").get("files").directory)
        self.test_subject.get("Mock Experiment").index()
        list(self.test_subject.get("Mock Experiment").get("files").files.values())[0].unlink()
        with pytest.raises(MissingFilesError):
            self.test_subject.validate()
