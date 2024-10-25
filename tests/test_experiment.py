from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from exporgo.experiment import Experiment, ExperimentFactory


@patch('exporgo.experiment.FileTree')
@patch('exporgo.experiment.get_timestamp', return_value="2023-01-01")
def experiment_initialization_creates_file_tree(mock_get_timestamp, mock_file_tree):
    experiment = Experiment(name="TestExperiment", base_directory=Path("/base/dir"))
    mock_file_tree.assert_called_with("TestExperiment", Path("/base/dir"))
    assert experiment._instance_date == "2023-01-01"

@patch('exporgo.experiment.FileTree')
def experiment_reindex_updates_file_tree(mock_file_tree):
    experiment = Experiment(name="TestExperiment", base_directory=Path("/base/dir"))
    experiment.reindex()
    experiment.file_tree.index.assert_called_once()

@patch('exporgo.experiment.FileTree')
def experiment_remap_changes_base_directory(mock_file_tree):
    experiment = Experiment(name="TestExperiment", base_directory=Path("/base/dir"))
    new_base_directory = Path("/new/base/dir")
    experiment.remap(new_base_directory)
    assert experiment._base_directory == new_base_directory
    experiment.file_tree.remap.assert_called_with(new_base_directory)

@patch('exporgo.experiment.FileTree')
def experiment_validate_calls_file_tree_validate(mock_file_tree):
    experiment = Experiment(name="TestExperiment", base_directory=Path("/base/dir"))
    experiment.validate()
    experiment.file_tree.validate.assert_called_once()

@patch('exporgo.experiment.FileTree')
def experiment_generate_file_tree_adds_paths(mock_file_tree):
    experiment = Experiment(name="TestExperiment", base_directory=Path("/base/dir"))
    experiment.generate_file_tree()
    experiment.file_tree.add_path.assert_any_call("results")
    experiment.file_tree.add_path.assert_any_call("figures")
    experiment.file_tree.build.assert_called_once()

def experiment_factory_adds_mix_ins_correctly():
    factory = ExperimentFactory(name="TestExperiment")
    factory.add_mix_ins(["TestMixIn"])
    assert len(factory._mix_ins) == 1

def experiment_factory_object_constructor_creates_experiment_class():
    factory = ExperimentFactory(name="TestExperiment")
    factory.add_mix_ins(["TestMixIn"])
    experiment_class = factory.object_constructor()
    assert experiment_class.__name__ == "TestExperiment"

def experiment_factory_instance_constructor_creates_experiment_instance():
    factory = ExperimentFactory(name="TestExperiment", base_directory=Path("/base/dir"))
    factory.add_mix_ins(["TestMixIn"])
    experiment_instance = factory.instance_constructor()
    assert isinstance(experiment_instance, Experiment)
    assert experiment_instance._name == "TestExperiment"
    assert experiment_instance._base_directory == Path("/base/dir")