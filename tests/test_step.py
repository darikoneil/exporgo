import inspect
from unittest.mock import MagicMock, patch

import pytest

# noinspection PyProtectedMember
from exporgo._io import import_function_from_file, select_file
from exporgo.exceptions import (AnalysisNotRegisteredError,
                                DuplicateRegistrationError)
from exporgo.step import (Category, RegisteredStep, Status, Step, StepRegistry,
                          ValidStep)
from exporgo.types import File


class TestValidStep:

    def test_serialize_call_with_callable(self):
        step = ValidStep(key="test", call=select_file, file_sets="files", category=Category.ANALYZE)
        result = step.serialize_call(select_file)
        assert result["name"] == "select_file"

    def test_serialize_call_with_path(self):
        step = ValidStep(key="test", call="path/to/file", file_sets="files", category=Category.ANALYZE)
        result = step.serialize_call("path/to/file")
        assert result == "path/to/file"

    def test_serialize_category(self):
        step = ValidStep(key="test", call="path/to/file", file_sets="files", category=Category.ANALYZE)
        result = step.serialize_category(Category.ANALYZE)
        assert result == "(ANALYZE, 1)"

    def test_serialize_status(self):
        step = ValidStep(key="test", call="path/to/file", file_sets="files", category=Category.ANALYZE, status=Status.SOURCE)
        result = step.serialize_status(Status.SOURCE)
        assert result == "(SOURCE, 0)"

    def test_validate_call_with_dict(self):
        with patch('exporgo._io.import_function_from_file') as mock_import:
            mock_import.return_value = lambda: "test"
            step = ValidStep(key="test", call={"name": "func", "file": "path/to/file"}, file_sets="files", category=Category.ANALYZE)
            result = step.validate_call({"name": "func", "file": "path/to/file"})
            assert result() == "test"

    def test_validate_call_with_callable(self):
        def select_file():
            pass

        step = ValidStep(key="test", call=select_file, file_sets="files", category=Category.ANALYZE)
        result = step.validate_call(select_file)
        assert result == select_file

    def test_validate_category(self):
        step = ValidStep(key="test", call="path/to/file", file_sets="files", category=Category.ANALYZE)
        result = step.validate_category("analyze")
        assert result == Category.ANALYZE

    def test_validate_status(self):
        step = ValidStep(key="test", call="path/to/file", file_sets="files", category=Category.ANALYZE)
        result = step.validate_status("source")
        assert result == Status.SOURCE


class TestStep:

    def test_initialize_step_with_valid_data(self):
        step = Step(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE, status=Status.SOURCE)
        assert step.key == "test_key"
        assert step.call == "path/to/file"
        assert step.file_sets == "files"
        assert step.category == Category.ANALYZE
        assert step.status == Status.SOURCE

    def test_call_method_executes_callable(self):
        mock_callable = MagicMock()
        step = Step(key="test_key", call=mock_callable, file_sets="files", category=Category.ANALYZE)
        file = File(path="dummy_path")
        step(file)
        mock_callable.assert_called_once_with(file)

    def test_call_method_raises_not_implemented_error_for_non_callable(self):
        step = Step(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE)
        file = File(path="dummy_path")
        with pytest.raises(NotImplementedError):
            step(file)

    def test_deserialize_creates_step_instance(self):
        step_data = {
            "key": "test_key",
            "call": "path/to/file",
            "file_sets": "files",
            "category": Category.ANALYZE,
            "status": Status.SOURCE
        }
        step = Step.__deserialize__(**step_data)
        assert step.key == "test_key"
        assert step.call == "path/to/file"
        assert step.file_sets == "files"
        assert step.category == Category.ANALYZE
        assert step.status == Status.SOURCE

    def test_serialize_returns_step_data(self):
        step = Step(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE, status=Status.SOURCE)
        serialized_data = Step.__serialize__(step)
        assert serialized_data["key"] == "test_key"
        assert serialized_data["call"] == "path/to/file"
        assert serialized_data["file_sets"] == "files"
        assert serialized_data["category"] == Category.ANALYZE
        assert serialized_data["status"] == Status.SOURCE

    def test_status_setter_updates_status(self):
        step = Step(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE, status=Status.SOURCE)
        step.status = Status.ANALYZE
        assert step.status == Status.ANALYZE


class TestRegisteredStep:

    def test_serialize_call_with_callable(self):

        step = RegisteredStep(key="test", call=select_file, file_sets="files", category=Category.ANALYZE)
        result = step.serialize_call(select_file)
        assert result["name"] == "select_file"
        assert result["file"] == inspect.getsourcefile(select_file)

    pytest.mark.skip(reason="Not implemented")
    def test_serialize_call_with_path(self):
        step = RegisteredStep(key="test", call=select_file, file_sets="files", category=Category.ANALYZE)
        # noinspection PyUnusedLocal
        result = step.serialize_call(select_file)

    def test_serialize_category(self):
        step = RegisteredStep(key="test", call=select_file, file_sets="files", category=Category.ANALYZE)
        result = step.serialize_category(Category.ANALYZE)
        assert result == "(ANALYZE, 1)"

    def test_validate_call_with_callable(self):

        step = RegisteredStep(key="test", call=select_file, file_sets="files", category=Category.ANALYZE)
        result = step.validate_call(select_file)
        assert result == select_file

    def test_validate_category(self):
        step = RegisteredStep(key="test", call=select_file, file_sets="files", category=Category.ANALYZE)
        result = step.validate_category(Category.ANALYZE)
        assert result == Category.ANALYZE


class TestStepRegistry:

    def test_save_registry_creates_file(self, tmp_path):
        registry_path = tmp_path / "registered_steps.json"
        StepRegistry._StepRegistry__path = registry_path
        StepRegistry._save_registry()
        assert registry_path.exists()

    def test_has_returns_true_for_registered_key(self):
        StepRegistry._StepRegistry__registry = {"test_key": RegisteredStep(key="test_key", call="call", file_sets="files", category=Category.ANALYZE)}
        assert StepRegistry.has("test_key") is True

    def test_has_returns_false_for_unregistered_key(self):
        StepRegistry._StepRegistry__registry = {}
        assert StepRegistry.has("test_key") is False

    def test_get_returns_registered_step(self):
        step = RegisteredStep(key="test_key", call="call", file_sets="files", category=Category.ANALYZE)
        StepRegistry._StepRegistry__registry = {"test_key": step}
        assert StepRegistry.get("test_key") == step

    def test_get_raises_error_for_unregistered_key(self):
        StepRegistry._StepRegistry__registry = {}
        with pytest.raises(AnalysisNotRegisteredError):
            StepRegistry.get("test_key")

    def test_pop_removes_and_returns_registered_step(self):
        step = RegisteredStep(key="test_key", call="call", file_sets="files", category=Category.ANALYZE)
        StepRegistry._StepRegistry__registry = {"test_key": step}
        assert StepRegistry.pop("test_key") == step
        assert "test_key" not in StepRegistry._StepRegistry__registry

    def test_pop_raises_error_for_unregistered_key(self):
        StepRegistry._StepRegistry__registry = {}
        with pytest.raises(AnalysisNotRegisteredError):
            StepRegistry.pop("test_key")

    def test_register_adds_new_step(self):
        StepRegistry._StepRegistry__registry = {}
        step = RegisteredStep(key="test_key", call="call", file_sets="files", category=Category.ANALYZE)
        StepRegistry.register(step)
        assert StepRegistry._StepRegistry__registry["test_key"] == step

    def test_register_raises_error_for_duplicate_key(self):
        step = RegisteredStep(key="test_key", call="call", file_sets="files", category=Category.ANALYZE)
        StepRegistry._StepRegistry__registry = {"test_key": step}
        with pytest.raises(DuplicateRegistrationError):
            StepRegistry.register(step)

    def test_load_registry_loads_existing_file(self, tmp_path):
        registry_path = tmp_path / "registered_steps.json"
        registry_path.write_text('{"test_key": {"key": "test_key", "call": "call", "file_sets": "files", "category": "ANALYZE"}}')
        StepRegistry._StepRegistry__path = registry_path
        StepRegistry._load_registry()
        # noinspection PyUnresolvedReferences
        assert "test_key" in StepRegistry._StepRegistry__registry

    def test_enter_loads_registry(self, tmp_path):
        registry_path = tmp_path / "registered_steps.json"
        registry_path.write_text('{"test_key": {"key": "test_key", "call": "call", "file_sets": "files", "category": "ANALYZE"}}')
        StepRegistry._StepRegistry__path = registry_path
        with StepRegistry() as registry:
            # noinspection PyUnresolvedReferences
            assert "test_key" in StepRegistry._StepRegistry__registry

    def test_exit_saves_registry_on_new_registration(self, tmp_path):
        registry_path = tmp_path / "registered_steps.json"
        StepRegistry._StepRegistry__path = registry_path
        StepRegistry._StepRegistry__new_registration = True
        with StepRegistry():
            pass
        assert registry_path.exists()
