from pathlib import Path
from types import MappingProxyType
from unittest.mock import MagicMock, patch

import pytest

from exporgo.organization.files import FileTree
from exporgo.organization.pipeline import (
    Pipeline,
    PipelineFactory,
    RegisteredPipeline,
    ValidPipeline,
)
from exporgo.organization.step import RegisteredStep, Step, StepRegistry

# noinspection PyProtectedMember
from exporgo.registry import generic_function_call
from exporgo.types import Category, Status


class TestValidPipeline:
    test_source_folder = Path.cwd().parent.joinpath("exporgo").joinpath("sources")

    test_steps = [
        Step(
            key="test_key0",
            call=generic_function_call,
            file_sets="files0",
            category=Category.ANALYZE,
            status=Status.SOURCE,
        ),
        Step(
            key="test_key1",
            call=generic_function_call,
            file_sets=("files0", "files1"),
            category=Category.ANALYZE,
            status=Status.SOURCE,
        ),
    ]

    def test_serialize_sources_returns_dict(self):
        sources = MappingProxyType({"files": str(self.test_source_folder)})
        serialized_sources = ValidPipeline.serialize_sources(sources)
        assert serialized_sources == {"files": str(self.test_source_folder)}

    def test_serialize_status_returns_str(self):
        status = Status.SOURCE
        serialized_status = ValidPipeline.serialize_status(status)
        assert serialized_status == Status.SOURCE.__serialize__()

    def test_serialize_steps_returns_list(self):
        serialized_steps = ValidPipeline.serialize_steps(self.test_steps)
        for idx, step in enumerate(serialized_steps):
            assert self.test_steps[idx].__serialize__(self.test_steps[idx]) == step

    def test_validate_sources_returns_mapping_proxy(self):
        sources = {"files": self.test_source_folder}
        validated_sources = ValidPipeline.validate_sources(sources)
        assert validated_sources == sources

    def test_validate_status(self):
        status = Status.SOURCE
        validated_status = ValidPipeline.validate_status(status.__serialize__())
        assert validated_status == status

    def test_validate_steps_returns_list(self):
        validated_steps = ValidPipeline.validate_steps(
            [step.__serialize__(step) for step in self.test_steps]
        )
        for idx, step in enumerate(validated_steps):
            assert self.test_steps[idx] == step

    def test_validate_step(self):
        validated_steps = ValidPipeline.validate_steps(
            self.test_steps[0].__serialize__(self.test_steps[0])
        )
        assert self.test_steps[0] == validated_steps


class TestPipeline:
    @pytest.fixture(scope="function", autouse=True)
    def setup_sources(self, simple_source, path_assets):
        self.base_sources = MappingProxyType(
            {
                "files0": None,
                "files1": path_assets,
                "files2": (simple_source, path_assets),
                "files3": [simple_source, path_assets],
                "files4": {simple_source, path_assets},
                "files5": (source_ for source_ in (simple_source, path_assets)),
            }
        )
        self.test_steps = [
            Step(
                key="test_key0",
                call=generic_function_call,
                file_sets="files0",
                category=Category.ANALYZE,
                status=Status.SOURCE,
            ),
            Step(
                key="test_key1",
                call=generic_function_call,
                file_sets=("files0", "files1"),
                category=Category.ANALYZE,
                status=Status.SOURCE,
            ),
            Step(
                key="test_key2",
                call=generic_function_call,
                file_sets="files2",
                category=Category.ANALYZE,
                status=Status.SOURCE,
            ),
            Step(
                key="test_key3",
                call=generic_function_call,
                file_sets="files3",
                category=Category.ANALYZE,
                status=Status.SOURCE,
            ),
            Step(
                key="test_key4",
                call=generic_function_call,
                file_sets="files4",
                category=Category.ANALYZE,
                status=Status.SOURCE,
            ),
            Step(
                key="test_key5",
                call=generic_function_call,
                file_sets="files5",
                category=Category.ANALYZE,
                status=Status.SOURCE,
            ),
        ]

        self.base_status = Status.SOURCE

    @pytest.fixture(scope="function", autouse=True)
    def create_file_tree(self, destination):
        self.file_tree = FileTree(
            destination, ("files0", "files1", "files2", "files3", "files4", "files5")
        )

    def test_initialize_pipeline_with_valid_data(self):
        pipeline = Pipeline(
            steps=self.test_steps, status=self.base_status, sources=self.base_sources
        )
        assert pipeline.steps == self.test_steps
        assert pipeline.status == self.base_status
        assert pipeline.sources == self.base_sources

    def test_add_source_updates_sources(self):
        pipeline = Pipeline(
            steps=self.test_steps, status=self.base_status, sources=self.base_sources
        )
        pipeline.add_source("files0", self.base_sources.get("files1"))
        assert pipeline.sources["files0"] == self.base_sources.get("files1")

    def test_status_returns_minimum_step_status(self):
        pipeline = Pipeline(
            steps=self.test_steps, status=self.base_status, sources=self.base_sources
        )
        pipeline.steps[1].status = Status.ANALYZE
        assert pipeline.status == Status.SOURCE

    def test_collect_all_file_sets(self, simple_source):
        pipeline = Pipeline(
            steps=self.test_steps, status=self.base_status, sources=self.base_sources
        )
        with patch(
            "exporgo.organization.pipeline.select_directory", return_value=simple_source
        ):
            pipeline.collect(self.file_tree)
            for step in pipeline.steps:
                assert step.status == Status.ANALYZE

            assert self.file_tree.num_files > 0
            assert self.file_tree.num_folders > 0
            for fileset in pipeline.file_sets:
                assert len(self.file_tree.get(fileset).files) > 0

    def test_deserialize_creates_pipeline_instance(self):
        sources = {"files": self.base_sources.get("files1")}
        pipeline_data = {
            "steps": [step.__serialize__(step) for step in self.test_steps],
            "status": self.base_status.__serialize__(),
            "sources": sources,
        }
        pipeline = Pipeline.__deserialize__(**pipeline_data)
        assert pipeline.steps == self.test_steps
        assert pipeline.status == self.base_status
        assert pipeline.sources == MappingProxyType(sources)

    def test_serialize_returns_pipeline_data(self):
        pipeline = Pipeline(
            steps=self.test_steps, status=self.base_status, sources=self.base_sources
        )
        serialized_pipeline = Pipeline.__serialize__(pipeline)
        for idx, step in enumerate(serialized_pipeline.get("steps")):
            assert step == self.test_steps[idx].__serialize__(self.test_steps[idx])
        assert serialized_pipeline.get("status") == pipeline.status.__serialize__()
        _ = serialized_pipeline.get("sources").pop("files5")
        comparison_sources = ValidPipeline.serialize_sources(self.base_sources)
        _ = comparison_sources.pop("files5")
        assert serialized_pipeline.get("sources") == comparison_sources


class TestRegisteredPipeline:
    test_steps = [
        RegisteredStep(
            key="test_key0",
            call=generic_function_call,
            file_sets="files0",
            category=Category.ANALYZE,
        ),
        RegisteredStep(
            key="test_key1",
            call=generic_function_call,
            file_sets=("files0", "files1"),
            category=Category.ANALYZE,
        ),
    ]

    def test_filesets_returns_set(self):
        registered_pipeline = RegisteredPipeline(steps=self.test_steps)
        assert registered_pipeline.file_sets == {"files0", "files1"}

    def test_serialize_steps_returns_list(self):
        serialized_steps = RegisteredPipeline.serialize_steps(self.test_steps)
        for idx, step in enumerate(serialized_steps):
            assert self.test_steps[idx].key == step

    def test_validate_steps_returns_list(self, path_steps):
        serialized_steps = RegisteredPipeline.serialize_steps(self.test_steps)
        StepRegistry._StepRegistry__path = path_steps
        with patch.object(StepRegistry, "get", return_value=self.test_steps):
            for idx, step in enumerate(
                RegisteredPipeline.validate_steps(serialized_steps)
            ):
                assert self.test_steps[idx] == step[idx]


# noinspection PyUnresolvedReferences
class TestPipelineFactory:
    @pytest.fixture(scope="function", autouse=True)
    def setup_class(self, path_steps):
        StepRegistry._StepRegistry__path = path_steps
        StepRegistry._StepRegistry__registry = {
            "step_0": RegisteredStep(
                key="step_0",
                call=generic_function_call,
                file_sets="files0",
                category=Category.ANALYZE,
            ),
            "step_1": RegisteredStep(
                key="step_1",
                call=generic_function_call,
                file_sets=("files0", "files1"),
                category=Category.ANALYZE,
            ),
        }

    def test_create_pipeline_from_registered_step(self):
        factory = PipelineFactory(steps=None)
        factory._registry = StepRegistry()
        factory.add_step(
            RegisteredStep(
                key="step_0",
                call=generic_function_call,
                file_sets="files0",
                category=Category.ANALYZE,
            )
        )
        pipeline = factory.create()
        assert isinstance(pipeline, Pipeline)
        assert pipeline.steps[0].key == "step_0"

    def test_create_pipeline_from_step(self):
        factory = PipelineFactory(steps=Step(**vars(StepRegistry.get("step_0"))))
        factory._registry = StepRegistry()
        pipeline = factory.create()
        assert isinstance(pipeline, Pipeline)
        assert pipeline.steps[0].key == "step_0"

    def test_create_pipeline_from_key(self):
        factory = PipelineFactory(steps=None)
        factory._registry = StepRegistry()
        factory.add_step("step_0")
        pipeline = factory.create()
        assert isinstance(pipeline, Pipeline)
        assert pipeline.steps[0].key == "step_0"

    def test_create_pipeline_from_collection(self):
        factory = PipelineFactory(steps=None)
        factory._registry = StepRegistry()
        factory.add_step("step_0")
        factory.add_step("step_1")

        pipeline = factory.create()
        assert isinstance(pipeline, Pipeline)
        assert pipeline.steps[0].key == "step_0"
        assert pipeline.steps[1].key == "step_1"

    def test_enter_loads_step_registry(self):
        with patch.object(
            StepRegistry, "_load_registry", MagicMock(StepRegistry._load_registry)
        ):
            # noinspection PyUnusedLocal
            with PipelineFactory(steps=None) as f:
                ...
            assert StepRegistry._load_registry.called
