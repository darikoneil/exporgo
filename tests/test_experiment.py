from unittest.mock import MagicMock, patch

# noinspection PyUnresolvedReferences
import pytest

from exporgo.experiment import (Experiment, ExperimentFactory,
                                ExperimentRegistry, RegisteredExperiment)
from exporgo.files import FileTree
from exporgo.pipeline import Pipeline, RegisteredPipeline
from exporgo.types import Folder, Priority, Status


class TestExperiment:

    def test_initialize_experiment_with_valid_data(self):
        file_tree = MagicMock(spec=FileTree)
        pipeline = MagicMock(spec=Pipeline)
        experiment = Experiment(name="test_experiment", parent_directory=Folder("parent_dir"), keys="key", file_tree=file_tree, pipeline=pipeline, priority=Priority.NORMAL)
        assert experiment.name == "test_experiment"
        assert experiment.parent_directory == Folder("parent_dir")
        assert experiment.keys == ("key",)
        assert experiment.file_tree == file_tree
        assert experiment.pipeline == pipeline
        assert experiment.priority == Priority.NORMAL

    def test_add_sources_updates_pipeline_sources(self):
        pipeline = MagicMock(spec=Pipeline)
        experiment = Experiment(name="test_experiment", parent_directory=Folder("parent_dir"), keys="key", file_tree=MagicMock(spec=FileTree), pipeline=pipeline)
        experiment.add_sources({"files": "new_source"})
        pipeline.add_source.assert_called_once_with("files", "new_source")

    def test_analyze_calls_pipeline_analyze(self):
        pipeline = MagicMock(spec=Pipeline)
        experiment = Experiment(name="test_experiment", parent_directory=Folder("parent_dir"), keys="key", file_tree=MagicMock(spec=FileTree), pipeline=pipeline)
        experiment.analyze()
        pipeline.analyze.assert_called_once()

    def test_collect_calls_pipeline_collect(self):
        file_tree = MagicMock(spec=FileTree)
        pipeline = MagicMock(spec=Pipeline)
        experiment = Experiment(name="test_experiment", parent_directory=Folder("parent_dir"), keys="key", file_tree=file_tree, pipeline=pipeline)
        experiment.collect()
        pipeline.collect.assert_called_once_with(file_tree)

    def test_find_returns_file_tree_generator(self):
        file_tree = MagicMock(spec=FileTree)
        experiment = Experiment(name="test_experiment", parent_directory=Folder("parent_dir"), keys="key", file_tree=file_tree, pipeline=MagicMock(spec=Pipeline))
        experiment.find("identifier")
        file_tree.find.assert_called_once_with("identifier")

    def test_get_returns_file_set(self):
        file_tree = MagicMock(spec=FileTree)
        experiment = Experiment(name="test_experiment", parent_directory=Folder("parent_dir"), keys="key", file_tree=file_tree, pipeline=MagicMock(spec=Pipeline))
        experiment.get("key")
        file_tree.get.assert_called_once_with("key")

    def test_index_calls_file_tree_index(self):
        file_tree = MagicMock(spec=FileTree)
        experiment = Experiment(name="test_experiment", parent_directory=Folder("parent_dir"), keys="key", file_tree=file_tree, pipeline=MagicMock(spec=Pipeline))
        experiment.index()
        file_tree.index.assert_called_once()

    def test_remap_updates_parent_directory(self):
        file_tree = MagicMock(spec=FileTree)
        experiment = Experiment(name="test_experiment", parent_directory=Folder("parent_dir"), keys="key", file_tree=file_tree, pipeline=MagicMock(spec=Pipeline))
        experiment.remap(Folder("new_parent_dir"))
        assert experiment.parent_directory == Folder("new_parent_dir")
        file_tree.remap.assert_called_once_with(Folder("new_parent_dir"))

    def test_validate_calls_file_tree_validate(self):
        file_tree = MagicMock(spec=FileTree)
        experiment = Experiment(name="test_experiment", parent_directory=Folder("parent_dir"), keys="key", file_tree=file_tree, pipeline=MagicMock(spec=Pipeline))
        experiment.validate()
        file_tree.validate.assert_called_once()

    def test_call_executes_pipeline_collect_or_analyze(self):
        pipeline = MagicMock(spec=Pipeline)
        experiment = Experiment(name="test_experiment", parent_directory=Folder("parent_dir"), keys="key", file_tree=MagicMock(spec=FileTree), pipeline=pipeline)
        assert experiment.pipeline.status == Status.COLLECT
        experiment()
        pipeline.collect.assert_called_once()
        assert experiment.pipeline.status == Status.ANALYZE
        experiment()
        pipeline.analyze.assert_called_once()


class TestExperimentFactory:

    def test_create_experiment_with_valid_data(self):
        with patch.object(ExperimentRegistry, 'get', return_value=RegisteredExperiment(key="key", additional_file_sets=None, pipeline=RegisteredPipeline(steps=[]))):
            factory = ExperimentFactory(name="test_experiment", parent_directory=Folder("parent_dir"))
            experiment = factory.create("key")
            assert experiment.name == "test_experiment"
            assert experiment.parent_directory == Folder("parent_dir")
            assert experiment.keys == ("key",)
            assert isinstance(experiment.file_tree, FileTree)
            assert isinstance(experiment.pipeline, Pipeline)

    def test_enter_loads_experiment_registry(self):
        with ExperimentFactory(name="test_experiment", parent_directory=Folder("parent_dir")) as factory:
            assert factory.registry is not None

    def test_exit_unloads_experiment_registry(self):
        with ExperimentFactory(name="test_experiment", parent_directory=Folder("parent_dir")) as factory:
            pass
        assert factory.registry is None
