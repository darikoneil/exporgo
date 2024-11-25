import inspect
from unittest.mock import MagicMock
from typing import Callable, Generator
import pytest
from pathlib import Path

from exporgo.registry import generic_function_call, PATH_STEPS
from exporgo.exceptions import (AnalysisNotRegisteredError,
                                DuplicateRegistrationError)
from exporgo.step import (Category, RegisteredStep, Status, Step, StepRegistry,
                          ValidStep)
from exporgo.tools import serialize_function
from uuid import uuid1


class TestValidStep:

    test_key = "test_key"
    test_call_callable = generic_function_call
    test_call_path = Path.cwd().joinpath("test_file")
    test_file_sets = "files"
    base_category = Category.ANALYZE
    base_status = Status.SOURCE
    test_step_case = ValidStep(key=test_key,
                            call=test_call_callable,
                            file_sets=test_file_sets,
                            category=base_category,
                            status=base_status)

    def test_serialize_call_with_callable(self):
        result = self.test_step_case.serialize_call(self.test_call_callable)
        assert result["name"] == "generic_function_call"

    def test_serialize_call_with_path(self):
        result = self.test_step_case.serialize_call(self.test_call_path)
        assert result == str(self.test_call_path)

    def test_serialize_category(self):
        result = self.test_step_case.serialize_category(Category.ANALYZE)
        assert result == Category.ANALYZE.__serialize__()

    def test_serialize_status(self):
        result = self.test_step_case.serialize_status(Status.SOURCE)
        assert result == Status.SOURCE.__serialize__()

    def test_validate_call_with_dict(self):
        result = self.test_step_case.validate_call(serialize_function(generic_function_call))
        assert inspect.signature(result).parameters == inspect.signature(generic_function_call).parameters

    def test_validate_call_with_callable(self):
        result = self.test_step_case.validate_call(generic_function_call)
        assert result == generic_function_call

    def test_validate_category(self):
        result = self.test_step_case.validate_category(Category.ANALYZE.value)
        assert result == Category.ANALYZE

    def test_validate_status(self):
        result = self.test_step_case.validate_status(Status.SOURCE.value)
        assert result == Status.SOURCE


class TestStep:

    test_key = "test_key"
    mock_callable = MagicMock(spec_set=Callable)
    mock_subject_file = Path.cwd().joinpath("test_file")
    test_file_sets = "files"
    base_category = Category.ANALYZE
    base_status = Status.SOURCE

    def test_initialize_step_with_valid_input(self):
        step = Step(key=self.test_key,
                    call=self.mock_callable,
                    file_sets=self.test_file_sets,
                    category=self.base_category,
                    status=self.base_status)
        assert step.key == self.test_key
        assert step.call == self.mock_callable
        assert step.file_sets == self.test_file_sets
        assert step.category == self.base_category
        assert step.status == self.base_status

    def test_call_method_executes_callable(self):
        step = Step(key=self.test_key,
                    call=self.mock_callable,
                    file_sets=self.test_file_sets,
                    category=self.base_category,
                    status=self.base_status)
        step(self.mock_subject_file)
        self.mock_callable.assert_called_once_with(self.mock_subject_file)

    def test_call_method_raises_not_implemented_error_for_file(self):
        step = Step(key=self.test_key,
                    call=self.mock_subject_file,
                    file_sets=self.test_file_sets,
                    category=self.base_category,
                    status=self.base_status)
        with pytest.raises(NotImplementedError):
            step(self.mock_subject_file)

    def test_deserialize_creates_step_instance(self):
        step_data = {
            "key": self.test_key,
            "call": generic_function_call,
            "file_sets": self.test_file_sets,
            "category": self.base_category,
            "status": self.base_status,
        }
        step = Step.__deserialize__(**step_data)
        assert step.key == self.test_key
        assert step.call == generic_function_call
        assert step.file_sets == self.test_file_sets
        assert step.category == self.base_category
        assert step.status == self.base_status

    def test_serialize_returns_step_data(self):
        step = Step(key=self.test_key,
                    call=generic_function_call,
                    file_sets=self.test_file_sets,
                    category=self.base_category,
                    status=self.base_status)
        serialized_data = Step.__serialize__(step)
        assert serialized_data["key"] == self.test_key
        assert serialized_data["call"] == serialize_function(generic_function_call)
        assert serialized_data["file_sets"] == self.test_file_sets
        assert serialized_data["category"] == self.base_category.__serialize__()
        assert serialized_data["status"] == self.base_status.__serialize__()

    def test_status_setter_updates_status(self):
        step = Step(key=self.test_key,
                    call=self.mock_callable,
                    file_sets=self.test_file_sets,
                    category=self.base_category,
                    status=self.base_status)
        step.status = Status.ANALYZE
        assert step.status == Status.ANALYZE


class TestRegisteredStep:
    test_key = "test_key"
    test_file_sets = "files"
    test_file = Path.cwd().joinpath("test_file")
    base_category = Category.ANALYZE
    base_status = Status.SOURCE
    test_registered_step_case = RegisteredStep(key=test_key,
                                            call=generic_function_call,
                                            file_sets=test_file_sets,
                                            category=base_category)

    def test_serialize_call_with_callable(self):
        result = self.test_registered_step_case.serialize_call(generic_function_call)
        assert result["name"] == "generic_function_call"
        assert result["file"] == inspect.getsourcefile(generic_function_call)

    def test_serialize_call_with_path(self):
        result = self.test_registered_step_case.serialize_call(self.test_file)
        assert result == str(self.test_file)

    def test_serialize_category(self):
        result = self.test_registered_step_case.serialize_category(self.base_category)
        assert result == self.base_category.__serialize__()

    def test_validate_call_with_callable(self):
        result = self.test_registered_step_case.validate_call(generic_function_call)
        assert result == generic_function_call

    def test_validate_category(self):
        result = self.test_registered_step_case.validate_category(Category.ANALYZE.value)
        assert result == Category.ANALYZE


def create_step_generator(steps) -> Generator["RegisteredStep", None, None]:
    for step in steps:
        yield step


#@pytest.mark.xfail(reason="Implementation of tests incomplete")
class TestStepRegistry:

    real_registry_path = PATH_STEPS

    @pytest.fixture(scope="function", autouse=True)
    def setup_class(self, path_steps):
        StepRegistry._StepRegistry__path = path_steps

    @staticmethod
    def create_step(key: str) -> "RegisteredStep":
        return RegisteredStep(key=key,
                              call=generic_function_call,
                              file_sets="files",
                              category=Category.ANALYZE)

    def test_save_registry_creates_file(self):
        StepRegistry._save_registry()
        # noinspection PyUnresolvedReferences
        assert StepRegistry._StepRegistry__path.exists()

    def test_has_returns_true_for_registered_key(self):
        key = "test_has_returns_true_for_registered_key"
        # noinspection PyUnresolvedReferences
        StepRegistry._StepRegistry__registry[key] = self.create_step(key)
        assert StepRegistry.has(key) is True

    def test_has_returns_false_for_unregistered_key(self):
        assert StepRegistry.has("test_has_returns_false_for_unregistered_key") is False

    def test_get_returns_registered_step(self):
        key = "test_get_returns_registered_step"
        # noinspection PyUnresolvedReferences
        StepRegistry._StepRegistry__registry[key] = self.create_step(key)
        assert StepRegistry.get(key).key == key

    def test_get_raises_error_for_unregistered_key(self):
        with pytest.raises(AnalysisNotRegisteredError):
            StepRegistry.get("test_get_raises_error_for_unregistered_key")

    def test_pop_removes_and_returns_registered_step(self):
        key = "test_pop_removes_and_returns_registered_step"
        # noinspection PyUnresolvedReferences
        StepRegistry._StepRegistry__registry[key] = self.create_step(key)
        assert StepRegistry.pop(key).key == key
        assert StepRegistry.has(key) is False

    def test_pop_raises_error_for_unregistered_key(self):
        with pytest.raises(AnalysisNotRegisteredError):
            StepRegistry.pop("test_pop_raises_error_for_unregistered_key")

    def test_register_raises_error_for_duplicate_key(self):
        key = "test_register_raises_error_for_duplicate_key"
        with pytest.raises(DuplicateRegistrationError):
            StepRegistry.register(self.create_step(key))
            StepRegistry.register(self.create_step(key))

    def test_register_registered_step(self):
        key = "test_register_registered_step"
        step = self.create_step(key)
        StepRegistry.register(step)
        assert StepRegistry.get(key) == step

    def test_register_dict(self):
        key = "test_register_dict"
        step = self.create_step(key)
        StepRegistry.register({"key": step.key,
                               "call": step.call,
                               "file_sets": step.file_sets,
                               "category": step.category})
        assert StepRegistry.get(key) == step

    def test_register_str(self):
        key = "test_register_str"
        step = self.create_step(key)
        StepRegistry.register(key, **{"call": step.call,
                                      "file_sets": step.file_sets,
                                      "category": step.category})
        assert StepRegistry.get(key) == step

    @pytest.mark.parametrize("collection_type", [list, tuple, set, create_step_generator])
    def test_register_multiple_steps(self, collection_type):
        keys = [f"uuid_{uuid1()}" for _ in range(3)]
        steps = [self.create_step(key) for key in keys]
        StepRegistry.register(collection_type(steps))
        for key, step in zip(keys, steps):
            assert StepRegistry.get(key) == step

    def test_load_and_save_registry(self):
        StepRegistry._StepRegistry__registry = {}
        key = "test_load_and_save_registry"
        step = self.create_step(key)
        StepRegistry.register(step)
        StepRegistry._save_registry()
        StepRegistry._StepRegistry__registry = {}
        StepRegistry._load_registry()
        assert StepRegistry.get(key) == step

    def test_enter_loads_registry(self):
        StepRegistry._load_registry = MagicMock(StepRegistry._load_registry)
        # noinspection PyUnusedLocal
        with StepRegistry() as registry:
            ...
        assert StepRegistry._load_registry.called

    def test_exit_saves_registry_on_new_registration(self):
        StepRegistry._save_registry = MagicMock(StepRegistry._save_registry)
        with StepRegistry() as registry:
            registry.register(self.create_step("test_exit_saves_registry_on_new_registration"))
        assert StepRegistry._save_registry.called
