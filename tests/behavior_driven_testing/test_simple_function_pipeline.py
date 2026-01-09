import csv

import pytest

from exporgo.organization.experiment import ExperimentRegistry, RegisteredExperiment
from exporgo.organization.step import RegisteredStep, StepRegistry
from exporgo.organization.subject import Subject
from exporgo.types import Category, Priority, Status
from tests.behavior_driven_testing.actions import (
    analyze_function,
    load_data,
    prepare_function,
    summarize_function,
)
from tests.conftest import path_experiments, path_steps, simple_action_attributes


def check_file_tree(
    source_attributes, action_attributes, test_class, test_subject: Subject
) -> None:
    experiment = test_subject.experiments.get(test_class.test_experiment_name)
    assert (
        experiment.file_tree.num_files
        == source_attributes.num_files_total_in_source
        + action_attributes.num_files_created
    )
    assert (
        len(experiment.file_tree.files.files)
        == source_attributes.num_files_total_in_source
        + action_attributes.num_files_in_files
    )
    assert (
        len(experiment.file_tree.results.files)
        == action_attributes.num_files_in_results
    )


def check_data(action_attributes, test_class, test_subject: Subject) -> None:
    experiment = test_subject.experiments.get(test_class.test_experiment_name)
    raw_header, raw_data = load_data(
        next(experiment.find(f"*{action_attributes.raw_filename}"))
    )
    assert raw_header == action_attributes.raw_header
    for a, b in zip(raw_data, action_attributes.raw_data):
        pytest.approx(a, b)
    results_header, results_data = load_data(
        next(experiment.find(f"*{action_attributes.results_filename}"))
    )
    assert results_header == action_attributes.results_header
    for a, b in zip(results_data, action_attributes.results_data):
        pytest.approx(a, b)


class TestSimpleFunctionPipeline:
    test_name = "test_simple_function_pipeline"
    base_directory = None
    test_study = "test_study"
    test_meta = {"meta_key": "meta_value"}
    base_priority = Priority.ABOVE_NORMAL
    test_extra = {"extra": "details"}
    test_experiment_name = "test_experiment"
    test_experiment_keys = "experiment_0"
    test_experiment_meta = {"experiment_meta_key": "experiment_meta_value"}
    test_experiment_priority = Priority.HIGH
    test_experiment_extra = {"experiment_extra": "details"}
    test_experiment_directory = None
    test_raw_files_directory = None
    subject_directory = None
    source_directory = None
    steps_registry_path = None
    experiment_registry_path = None
    registered_steps = None
    registered_pipeline = None
    registered_experiment = None
    step_0 = {
        "key": "step_0",
        "call": prepare_function,
        "file_sets": "files",
        "category": Category.PREPARE,
    }
    step_1 = {
        "key": "step_1",
        "call": analyze_function,
        "file_sets": "files",
        "category": Category.ANALYZE,
    }
    step_2 = {
        "key": "step_2",
        "call": summarize_function,
        "file_sets": "files",
        "category": Category.SUMMARIZE,
    }
    steps = [step_0, step_1, step_2]
    source_attributes = None
    action_attributes = None

    @staticmethod
    def create_data(save_folder, action_attributes):
        header = action_attributes.raw_header
        data = action_attributes.raw_data
        filename = save_folder.joinpath(action_attributes.raw_filename)
        with open(filename, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(header)
            writer.writerows(data)

    @pytest.fixture(scope="function", autouse=True)
    def setup_class(
        self,
        tmp_path,
        simple_source,
        simple_source_attributes,
        simple_action_attributes,
        path_steps,
        path_experiments,
    ):
        self.base_directory = tmp_path
        self.source_directory = simple_source
        self.subject_directory = self.base_directory
        self.test_experiment_directory = self.subject_directory.joinpath(
            self.test_experiment_name
        )
        self.test_raw_files_directory = self.test_experiment_directory.joinpath("files")
        self.test_raw_files_directory.mkdir(parents=True, exist_ok=True)
        self.steps_registry_path = path_steps
        self.experiment_registry_path = path_experiments
        StepRegistry._StepRegistry__path = self.steps_registry_path
        self.registered_steps = []
        for step in self.steps:
            self.registered_steps.append(RegisteredStep(**step))
        self.registered_pipeline = {
            "steps": self.registered_steps,
        }
        ExperimentRegistry._ExperimentRegistry__path = self.experiment_registry_path
        self.registered_experiment = RegisteredExperiment(
            key="experiment_0",
            additional_file_sets="results",
            pipeline=self.registered_pipeline,
        )
        self.source_attributes = simple_source_attributes
        self.action_attributes = simple_action_attributes
        self.create_data(self.test_raw_files_directory, self.action_attributes)

    def test_simple_function_pipeline(self):
        # register steps and experiment
        with StepRegistry() as step_registry:
            step_registry.register(self.registered_steps)
        with ExperimentRegistry() as experiment_registry:
            experiment_registry.register(self.registered_experiment)
        # instantiate subject and experiment
        test_subject = Subject(
            name=self.test_name,
            directory=self.base_directory,
            study=self.test_study,
            meta=self.test_meta,
            priority=self.base_priority,
            **self.test_extra,
        )
        test_subject.create_experiment(
            name=self.test_experiment_name,
            keys=self.test_experiment_keys,
            meta=self.test_experiment_meta,
            priority=self.test_experiment_priority,
            **self.test_experiment_extra,
        )
        experiment = test_subject.experiments.get(self.test_experiment_name)
        experiment.add_sources("files", self.source_directory)

        # execute
        experiment.collect()
        experiment.analyze()

        # check
        assert experiment.status == Status.SUCCESS
        check_file_tree(
            self.source_attributes, self.action_attributes, self, test_subject
        )
        check_data(self.action_attributes, self, test_subject)
