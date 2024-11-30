from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid1

# noinspection PyUnresolvedReferences
import pytest

from exporgo.exceptions import (DuplicateRegistrationError,
                                ExperimentNotRegisteredError)
from exporgo.experiment import (Experiment, ExperimentFactory,
                                ExperimentRegistry, RegisteredExperiment,
                                ValidExperiment)
from exporgo.files import FileTree
from exporgo.pipeline import Pipeline, RegisteredPipeline
# noinspection PyProtectedMember
from exporgo.registry import generic_function_call
from exporgo.step import RegisteredStep, Step, StepRegistry
from exporgo.types import Category, Priority, Status
from tests.conftest import BlockPrinting


class TestValidExperiment:

    test_source_folder = Path.cwd().parent.joinpath("exporgo").joinpath("sources")

    name = "fake_experiment"
    keys = "generic_experiment"
    priority = Priority.NORMAL
    status = Status.SOURCE
    meta = {"meta_key": "meta_value"}
    file_tree = None
    pipeline = None
    parent_directory = None

    @pytest.fixture(scope="function", autouse=True)
    def setup_valid_experiment(self, tmp_path):
        self.file_tree = MagicMock(spec=FileTree)
        self.parent_directory = tmp_path
        self.pipeline = MagicMock(spec=Pipeline)

    def test_serialize_file_tree(self):
        _ = ValidExperiment.serialize_file_tree(self.file_tree)
        assert self.file_tree.__serialize__.called_once

    def test_serialize_parent_directory(self):
        serialized_parent_directory = ValidExperiment.serialize_parent_directory(self.parent_directory)
        assert isinstance(serialized_parent_directory, str)

    def test_serialize_pipeline(self):
        _ = ValidExperiment.serialize_pipeline(self.pipeline)
        assert self.pipeline.__serialize__.called_once

    def test_serialize_priority(self):
        serialized_priority = ValidExperiment.serialize_priority(self.priority)
        assert serialized_priority == Priority.__serialize__(self.priority)

    def test_serialize_status(self):
        serialized_status = ValidExperiment.serialize_status(self.status)
        assert serialized_status == Status.__serialize__(self.status)

    def test_validate_file_tree(self):
        _ = ValidExperiment.validate_file_tree(FileTree(Path.cwd(), "files").__serialize__())
        assert self.file_tree.validate.called_once

    def test_validate_pipeline(self):
        p = Pipeline(steps=[])
        _ = ValidExperiment.validate_pipeline(Pipeline.__serialize__(p))
        assert self.pipeline.__deserialize__.called_once

    def test_validate_priority(self):
        with patch("exporgo.experiment.Priority.__deserialize__", return_value=Priority.NORMAL) as mock_validate_priority:
            _ = ValidExperiment.validate_priority(Priority.NORMAL.__serialize__())
            mock_validate_priority.assert_called_once_with(Priority.NORMAL.__serialize__())

    def test_validate_status(self):
        with patch("exporgo.experiment.Status.__deserialize__", return_value=Status.SOURCE) as mock_validate_status:
            _ = ValidExperiment.validate_status(Status.SOURCE.__serialize__())
            mock_validate_status.assert_called_once_with(Status.SOURCE.__serialize__())


# noinspection PyUnresolvedReferences
class TestMockExperiment:

    name = "fake_experiment"
    key = "generic_experiment"
    priority = Priority.NORMAL
    file_tree = None
    pipeline = None

    @pytest.fixture(scope="function", autouse=True)
    def setup_dummy_experiment(self, tmp_path):
        self.experiment = Experiment(name=self.name,
                          parent_directory=tmp_path,
                          keys=self.key,
                          file_tree=MagicMock(spec=FileTree),
                          pipeline=MagicMock(spec=Pipeline),
                          priority=self.priority)

    def test_experiment_directories(self, tmp_path):
        assert self.experiment.parent_directory == tmp_path
        assert self.experiment.experiment_directory == tmp_path.joinpath(self.name)

    def test_add_sources_updates_pipeline_sources_dispatched_one_arg(self, tmp_path):
        self.experiment.add_sources({"files": "new_source"})
        self.experiment.pipeline.add_source.assert_called_once_with("files", "new_source")
        _ = self.experiment.sources
        # noinspection PyStatementEffect
        self.experiment.pipeline.sources.assert_called_once

    def test_add_sources_updates_pipeline_sources_dispatched_two_args(self, tmp_path):
        self.experiment.add_sources("files", "new_source")
        self.experiment.pipeline.add_source.assert_called_once_with("files", "new_source")
        _ = self.experiment.sources
        # noinspection PyStatementEffect
        self.experiment.pipeline.sources.assert_called_once

    def test_analyze_calls_pipeline_analyze(self):
        self.experiment.analyze()
        self.experiment.pipeline.analyze.assert_called_once()

    def test_collect_calls_pipeline_collect(self):
        self.experiment.collect()
        self.experiment.pipeline.collect.assert_called_once_with(self.experiment.file_tree)

    def test_find_returns_file_tree_generator(self):
        _ = self.experiment.find("identifier")
        self.experiment.file_tree.find.assert_called_once_with("identifier")

    def test_get_returns_file_set(self):
        _ = self.experiment.get("files")
        assert self.experiment.file_tree.get.called_once_with("key")

    def test_index_calls_file_tree_index(self):
        self.experiment.index()
        self.experiment.file_tree.index.assert_called_once()

    def test_remap_updates_parent_directory(self, tmp_path):
        self.experiment.remap(Path().cwd())
        assert self.experiment.parent_directory == Path.cwd()
        self.experiment.file_tree.remap.assert_called_once_with(Path.cwd())
        self.experiment.parent_directory = tmp_path
        assert self.experiment.parent_directory == tmp_path
        self.experiment.file_tree.remap.assert_called_with(tmp_path)

    def test_validate_calls_file_tree_validate(self):
        self.experiment.validate()
        self.experiment.file_tree.validate.assert_called_once()


class TestIntegratedExperiment:
    key = "generic_experiment"
    name = "integrated_experiment"
    priority = Priority.NORMAL

    def test_experiment_created(self, tmp_path):
        with patch("exporgo.experiment.get_timestamp", return_value="Timestamp") as get_timestamp_:
            # noinspection DuplicatedCode
            experiment = Experiment(name=self.name,
                                    parent_directory=tmp_path,
                                    keys=self.key,
                                    file_tree=FileTree(tmp_path, "files"),
                                    pipeline=Pipeline(steps=[Step(key="generic",
                                                                  call=generic_function_call,
                                                                  file_sets="files",
                                                                  category=Category.ANALYZE), ]),
                                    priority=self.priority)
            assert experiment.name == self.name
            assert experiment.keys == (self.key,)
            assert experiment.priority == Priority.NORMAL
            assert get_timestamp_.called_once

    def test_print_experiment(self, tmp_path):
        # noinspection DuplicatedCode
        experiment = Experiment(name=self.name,
                                parent_directory=tmp_path,
                                keys=self.key,
                                file_tree=FileTree(tmp_path, "files"),
                                pipeline=Pipeline(steps=[Step(key="generic",
                                                              call=generic_function_call,
                                                              file_sets="files",
                                                              category=Category.ANALYZE), ]),
                                priority=self.priority,
                                meta={"meta_key": "meta_value"})
        with BlockPrinting():
            print(experiment)
        experiment.meta = {}
        with BlockPrinting():
            print(experiment)

    @pytest.mark.xfail(reason="Needs implemented")
    def test_experiment_calls_pipeline_source_to_collect(self, tmp_path, simple_source):
        # noinspection DuplicatedCode
        experiment = Experiment(name=self.name,
                                parent_directory=tmp_path,
                                keys=self.key,
                                file_tree=FileTree(tmp_path, "files"),
                                pipeline=Pipeline(steps=[Step(key="generic",
                                                              call=generic_function_call,
                                                              file_sets="files",
                                                              category=Category.ANALYZE), ]),
                                priority=self.priority)
        assert experiment.status == Status.SOURCE
        experiment.add_sources({"files": simple_source})
        assert experiment.pipeline.status == Status.COLLECT

    def test_experiment_pipeline_collect_to_analyze(self, tmp_path, simple_source):
        # noinspection DuplicatedCode
        experiment = Experiment(name=self.name,
                                parent_directory=tmp_path,
                                keys=self.key,
                                file_tree=FileTree(tmp_path, "files"),
                                pipeline=Pipeline(steps=[Step(key="generic",
                                                              call=generic_function_call,
                                                              file_sets="files",
                                                              category=Category.ANALYZE), ]),
                                priority=self.priority)
        experiment.add_sources({"files": simple_source})
        for step in experiment.pipeline.steps:
            step.status = Status.COLLECT
        assert experiment.status == Status.COLLECT
        experiment.collect()
        assert experiment.file_tree.num_files > 0
        assert experiment.pipeline.status == Status.ANALYZE

    def test_experiment_pipeline_analyze_to_success(self, tmp_path, simple_source):
        # noinspection DuplicatedCode
        experiment = Experiment(name=self.name,
                                parent_directory=tmp_path,
                                keys=self.key,
                                file_tree=FileTree(tmp_path, "files"),
                                pipeline=Pipeline(steps=[Step(key="generic",
                                                              call=generic_function_call,
                                                              file_sets="files",
                                                              category=Category.ANALYZE), ]),
                                priority=self.priority)
        experiment.add_sources({"files": simple_source})
        for step in experiment.pipeline.steps:
            step.status = Status.ANALYZE
        assert experiment.status == Status.ANALYZE
        with BlockPrinting():
            experiment.analyze()
        assert experiment.pipeline.status == Status.SUCCESS


class TestRegisteredExperiment:

    key = "TestRegisteredExperiment"
    pipeline = RegisteredPipeline(steps=[RegisteredStep(key="generic",
                                                call=generic_function_call,
                                                file_sets="files",
                                                category=Category.ANALYZE), ])

    @pytest.mark.parametrize("additional_file_sets", [None, ["additional_files"], ["files", "additional_files"]])
    def test_with_additional_file_sets(self, additional_file_sets):
        experiment = RegisteredExperiment(key=self.key,
                                          additional_file_sets=additional_file_sets,
                                          pipeline=self.pipeline)
        assert experiment.file_sets == set(["files"] + (additional_file_sets or []))


def create_experiment_generator(experiments):
    for experiment in experiments:
        yield experiment


class TestExperimentRegistry:

    @pytest.fixture(scope="function", autouse=True)
    def setup_class(self, path_steps, path_experiments):
        StepRegistry._StepRegistry__path = path_steps
        StepRegistry._StepRegistry__registry = {
            "generic_step_0": RegisteredStep(key="generic_step_0",
                                             call=generic_function_call,
                                             file_sets="files",
                                             category=Category.ANALYZE),
            "generic_step_1": RegisteredStep(key="generic_step_1",
                                             call=generic_function_call,
                                             file_sets="files",
                                             category=Category.ANALYZE),
        }
        ExperimentRegistry._ExperimentRegistry__path = path_experiments

    @staticmethod
    def create_experiment(key: str) -> RegisteredExperiment:
        return RegisteredExperiment(key=key,
                                    additional_file_sets=None,
                                    pipeline=RegisteredPipeline(steps=[StepRegistry.get("generic_step_0"),
                                                                       StepRegistry.get("generic_step_1")])
                                    )

    def test_save_registry_creates_file(self):
        ExperimentRegistry._save_registry()
        # noinspection PyUnresolvedReferences
        assert ExperimentRegistry._ExperimentRegistry__path.exists()

    def test_has_returns_true_for_registered_key(self):
        key = "test_has_returns_true_for_registered_key"
        # noinspection PyUnresolvedReferences
        ExperimentRegistry._ExperimentRegistry__registry[key] = self.create_experiment(key)
        assert ExperimentRegistry.has(key) is True

    def test_has_returns_false_for_unregistered_key(self):
        assert ExperimentRegistry.has("test_has_returns_false_for_unregistered_key") is False

    def test_get_returns_registered_experiment(self):
        key = "test_get_returns_registered_experiment"
        # noinspection PyUnresolvedReferences
        ExperimentRegistry._ExperimentRegistry__registry[key] = self.create_experiment(key)
        assert ExperimentRegistry.get(key).key == key

    def test_get_raises_error_for_unregistered_key(self):
        with pytest.raises(ExperimentNotRegisteredError):
            ExperimentRegistry.get("test_get_raises_error_for_unregistered_key")

    def test_pop_removes_and_returns_registered_experiment(self):
        key = "test_pop_removes_and_returns_registered_experiment"
        # noinspection PyUnresolvedReferences
        ExperimentRegistry._ExperimentRegistry__registry[key] = self.create_experiment(key)
        assert ExperimentRegistry.pop(key).key == key
        assert ExperimentRegistry.has(key) is False

    def test_pop_raises_error_for_unregistered_key(self):
        with pytest.raises(ExperimentNotRegisteredError):
            ExperimentRegistry.pop("test_pop_raises_error_for_unregistered_key")

    def test_register_raises_error_for_duplicate_key(self):
       key = "test_register_raises_error_for_duplicate_key"
       with pytest.raises(DuplicateRegistrationError):
           ExperimentRegistry.register(self.create_experiment(key))
           ExperimentRegistry.register(self.create_experiment(key))

    def test_register_registered_experiment(self):
        key = "test_register_registered_experiment"
        experiment = self.create_experiment(key)
        ExperimentRegistry.register(experiment)
        assert ExperimentRegistry.get(key) == experiment

    def test_register_dict(self):
        key = "test_register_dict"
        experiment = self.create_experiment(key)
        ExperimentRegistry.register({"key": experiment.key,
                                     "additional_file_sets": experiment.additional_file_sets,
                                     "pipeline": experiment.pipeline})
        assert ExperimentRegistry.get(key) == experiment

    def test_register_str(self):
        key = "test_register_str"
        experiment = self.create_experiment(key)
        ExperimentRegistry.register(key, **{"additional_file_sets": experiment.additional_file_sets,
                                            "pipeline": experiment.pipeline})
        assert ExperimentRegistry.get(key) == experiment

    @pytest.mark.parametrize("collection_type", [list, tuple, set, create_experiment_generator])
    def test_register_multiple_steps(self, collection_type):
        keys = [f"uuid_{uuid1()}" for _ in range(3)]
        experiments = [self.create_experiment(key) for key in keys]
        ExperimentRegistry.register(collection_type(experiments))
        for key, experiment in zip(keys, experiments):
           assert ExperimentRegistry.get(key) == experiment

    def test_load_and_save_registry(self):
        ExperimentRegistry._ExperimentRegistry__registry = {}
        key = "test_load_and_save_registry"
        experiment = self.create_experiment(key)
        ExperimentRegistry.register(experiment)
        ExperimentRegistry._save_registry()
        ExperimentRegistry._ExperimentRegistry__registry = {}
        ExperimentRegistry._load_registry()
        assert ExperimentRegistry.get(key) == experiment

    def test_enter_loads_registry(self):
        with patch.object(ExperimentRegistry, '_load_registry', MagicMock(ExperimentRegistry._load_registry)):
            # noinspection PyUnusedLocal
            with ExperimentRegistry() as registry:
                ...
            # noinspection PyUnresolvedReferences
            assert ExperimentRegistry._load_registry.called

    def test_exit_saves_registry_on_new_registration(self):
        with patch.object(ExperimentRegistry, '_save_registry', MagicMock(ExperimentRegistry._save_registry)):
            with ExperimentRegistry() as registry:
                registry.register(self.create_experiment("test_exit_saves_registry_on_new_registration"))
            # noinspection PyUnresolvedReferences
            assert ExperimentRegistry._save_registry.called


class TestExperimentFactory:

    @pytest.fixture(scope="function", autouse=True)
    def setup_class(self, path_steps, path_experiments):
        StepRegistry._StepRegistry__path = path_steps
        StepRegistry._StepRegistry__registry = {
            "generic_step_0": RegisteredStep(key="generic_step_0",
                                             call=generic_function_call,
                                             file_sets="files",
                                             category=Category.ANALYZE),
            "generic_step_1": RegisteredStep(key="generic_step_1",
                                             call=generic_function_call,
                                             file_sets="files",
                                             category=Category.ANALYZE),
        }
        ExperimentRegistry._ExperimentRegistry__path = path_experiments

    @staticmethod
    def create_experiment(key: str) -> RegisteredExperiment:
        return RegisteredExperiment(key=key,
                                    additional_file_sets=None,
                                    pipeline=RegisteredPipeline(steps=[StepRegistry.get("generic_step_0"),
                                                                       StepRegistry.get("generic_step_1")]),
                                    )

    def test_create_experiment_with_valid_data(self, tmp_path):
        with patch.object(ExperimentRegistry, 'get',
                          return_value=self.create_experiment("test_create_experiment_with_valid_data")):
            factory = ExperimentFactory(name="test_experiment",
                                        parent_directory=tmp_path,
                                        priority=Priority.CRITICAL,
                                        meta={"meta_key": "meta_value"})
            factory._ExperimentFactory__registry = ExperimentRegistry()
            experiment = factory.create("test_create_experiment_with_valid_data")
            assert experiment.name == "test_experiment"
            assert experiment.parent_directory == tmp_path
            assert experiment.keys == ("test_create_experiment_with_valid_data", )
            assert experiment.priority == Priority.CRITICAL
            assert experiment.meta == {"meta_key": "meta_value"}
            assert isinstance(experiment.file_tree, FileTree)
            assert isinstance(experiment.pipeline, Pipeline)

    def test_enter_loads_experiment_registry(self, tmp_path):
        with patch.object(ExperimentRegistry, '_load_registry', MagicMock(ExperimentRegistry._load_registry)):
            # noinspection PyUnusedLocal
            with ExperimentFactory(name="test_experiment",
                                   parent_directory=tmp_path
                                   ) as factory:
                ...
            # noinspection PyUnresolvedReferences
            assert ExperimentRegistry._load_registry.called

    def test_exit_unloads_experiment_registry(self, tmp_path):
        with patch.object(ExperimentRegistry, '_save_registry', MagicMock(ExperimentRegistry._save_registry)):
            # noinspection PyUnusedLocal
            with ExperimentFactory(name="test_experiment",
                                   parent_directory=tmp_path
                                   ) as factory:
                ...
            assert factory._ExperimentFactory__registry is None
