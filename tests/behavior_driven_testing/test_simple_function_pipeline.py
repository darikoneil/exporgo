import pytest

from exporgo.step import RegisteredStep, StepRegistry
from exporgo.subject import Subject
from exporgo.types import Priority, Category
from tests.behavior_driven_testing.actions import prepare_function, analyze_function, summarize_function


class TestSimpleFunctionPipeline:
    base_directory = None
    source_directory = None
    steps_registry_path = None
    experiment_registry_path = None
    registered_steps = None
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
        "file_sets": ("files", "results"),
        "category": Category.SUMMARIZE,
    }
    steps = [step_0, step_1, step_2]

    @pytest.fixture(scope="function", autouse=True)
    def setup_class(self, tmp_path, source, steps_registry_path, experiment_registry_path):
        self.base_directory = tmp_path
        self.source_directory = source
        self.steps_registry_path = steps_registry_path
        self.experiment_registry_path = experiment_registry_path

    @pytest.fixture(scope="function", autouse=True)
    def setup_registering_steps(self):
        StepRegistry._StepRegistry__path = self.steps_registry_path
        self.registered_steps = []
        for step in self.steps:
            self.registered_steps.append(RegisteredStep(**step))

    @pytest.fixture(scope="function", autouse=True)
    def setup_registering_experiments(self):
        pass

    def test_simple_function_pipeline(self):
        pass

def test_simple_function_pipeline(tmp_path, source):
    # test_subject = Subject(name="Test Subject",
    #                       directory=tmp_path,
    #                       study="Test Study",
    #                       meta={"test": "details"},
    #                       priority=Priority.NORMAL,
    #                      extra="extra details")
    # test_subject.create_experiment("Test Experiment")
