from pathlib import Path
from types import MappingProxyType
from unittest.mock import MagicMock, patch

import pytest

from exporgo.files import FileTree
from exporgo.pipeline import (Pipeline, PipelineFactory, RegisteredPipeline,
                              ValidPipeline)
from exporgo.registry import generic_function_call
from exporgo.step import RegisteredStep, Step, StepRegistry
from exporgo.types import Category, Status


class TestValidPipeline:

        test_source_folder = Path.cwd().parent.joinpath("exporgo").joinpath("sources")

        test_steps = [Step(key="test_key0",
                         call=generic_function_call,
                         file_sets="files0",
                         category=Category.ANALYZE,
                         status=Status.SOURCE),
                        Step(key="test_key1",
                            call=generic_function_call,
                            file_sets=("files0", "files1"),
                            category=Category.ANALYZE,
                            status=Status.SOURCE)]

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
                assert self.test_steps[idx].__serialize__(self.test_steps[idx]) ==  step

        def test_validate_sources_returns_mapping_proxy(self):
            sources = {"files": self.test_source_folder}
            validated_sources = ValidPipeline.validate_sources(sources)
            assert validated_sources == sources

        def test_validate_status(self):
            status = Status.SOURCE
            validated_status = ValidPipeline.validate_status(status.__serialize__())
            assert validated_status == status

        def test_validate_steps_returns_list(self):
            validated_steps = ValidPipeline.validate_steps([step.__serialize__(step)
                                                            for step in self.test_steps])
            for idx, step in enumerate(validated_steps):
                assert self.test_steps[idx] == step


class TestPipeline:

    test_steps = [Step(key="test_key0",
                        call=generic_function_call,
                        file_sets="files0",
                        category=Category.ANALYZE,
                        status=Status.SOURCE),
                    Step(key="test_key1",
                        call=generic_function_call,
                        file_sets=("files0", "files1"),
                        category=Category.ANALYZE,
                        status=Status.SOURCE),
                    Step(key="test_key2",
                        call=generic_function_call,
                        file_sets="files2",
                        category=Category.ANALYZE,
                        status=Status.SOURCE),
                    Step(key="test_key3",
                        call=generic_function_call,
                        file_sets="files3",
                        category=Category.ANALYZE,
                        status=Status.SOURCE),
                    Step(key="test_key4",
                        call=generic_function_call,
                        file_sets="files4",
                        category=Category.ANALYZE,
                        status=Status.SOURCE),
                    Step(key="test_key5",
                        call=generic_function_call,
                        file_sets="files5",
                        category=Category.ANALYZE,
                        status=Status.SOURCE)]

    base_status = Status.SOURCE
    base_sources = MappingProxyType({"files0": None,
                                     "files1": Path.cwd().parent.joinpath("exporgo").parent.joinpath("exporgo").joinpath("schemas"),
                                     "files2": (Path.cwd().parent.joinpath("exporgo").joinpath("registry"),
                                                Path.cwd().parent.joinpath("exporgo").joinpath("schemas")),
                                     "files3": [Path.cwd().parent.joinpath("exporgo").joinpath("schemas"),
                                                Path.cwd().parent.joinpath("exporgo").joinpath("registry")],
                                     "files4": {Path.cwd().parent.joinpath("exporgo").joinpath("registry"),
                                                Path.cwd().parent.joinpath("exporgo").joinpath("schemas")},
                                     "files5": (path_ for path_ in (Path.cwd().parent.joinpath("exporgo").joinpath("schemas"),
                                                                    Path.cwd().parent.joinpath("exporgo").joinpath("registry")))})
    additional_source_path = Path.cwd().parent.joinpath("exporgo").joinpath("registry")

    @pytest.fixture(scope="function", autouse=True)
    def create_file_tree(self, destination):
        self.file_tree = FileTree(destination, ("files0", "files1", "files2", "files3", "files4", "files5"))

    def test_initialize_pipeline_with_valid_data(self):
        pipeline = Pipeline(steps=self.test_steps,
                            status=self.base_status,
                            sources=self.base_sources)
        assert pipeline.steps == self.test_steps
        assert pipeline.status == self.base_status
        assert pipeline.sources == self.base_sources

    def test_add_source_updates_sources(self):
        pipeline = Pipeline(steps=self.test_steps,
                            status=self.base_status,
                            sources=self.base_sources)
        pipeline.add_source("files0", self.additional_source_path)
        assert pipeline.sources["files0"] == self.additional_source_path

    def test_status_returns_minimum_step_status(self):
        pipeline = Pipeline(steps=self.test_steps,
                            status=self.base_status,
                            sources=self.base_sources)
        pipeline.steps[1].status = Status.ANALYZE
        assert pipeline.status == Status.SOURCE

    def test_collect_all_file_sets(self, source):
        pipeline = Pipeline(steps=self.test_steps,
                            status=self.base_status,
                            sources=self.base_sources)
        with patch("exporgo.pipeline.select_directory", return_value=source):
            pipeline.collect(self.file_tree)
            for step in pipeline.steps:
                assert step.status == Status.ANALYZE

            assert self.file_tree.num_files > 0
            assert self.file_tree.num_folders > 0
            for fileset in pipeline.file_sets:
                assert len(self.file_tree.get(fileset).files) > 0
                assert len(self.file_tree.get(fileset).folders) >= 0

    @pytest.mark.xfail(reason="Need to implement")
    def test_deserialize_creates_pipeline_instance(self):
        pipeline_data = {
            "steps": [Step(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE, status=Status.SOURCE)],
            "status": Status.SOURCE,
            "sources": dict({"files": None})
        }
        pipeline = Pipeline.__deserialize__(**pipeline_data)
        assert pipeline.steps == pipeline_data["steps"]
        assert pipeline.status == pipeline_data["status"]
        assert pipeline.sources == pipeline_data["sources"]


    def test_serialize_returns_pipeline_data(self):
        pipeline = Pipeline(steps=self.test_steps,
                            status=self.base_status,
                            sources=self.base_sources)
        serialized_pipeline = Pipeline.__serialize__(pipeline)
        for idx, step in enumerate(serialized_pipeline.get("steps")):
            assert step == self.test_steps[idx].__serialize__(self.test_steps[idx])
        assert serialized_pipeline.get("status") == pipeline.status.__serialize__()
        _ = serialized_pipeline.get("sources").pop("files5")
        comparison_sources = ValidPipeline.serialize_sources(self.base_sources)
        _ = comparison_sources.pop("files5")
        assert serialized_pipeline.get("sources") == comparison_sources


class TestRegisteredPipeline:
    test_steps = [RegisteredStep(key="test_key0",
                                    call=generic_function_call,
                                    file_sets="files0",
                                    category=Category.ANALYZE),
                    RegisteredStep(key="test_key1",
                                    call=generic_function_call,
                                    file_sets=("files0", "files1"),
                                    category=Category.ANALYZE)]

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
            for idx, step in enumerate(RegisteredPipeline.validate_steps(serialized_steps)):
                assert self.test_steps[idx] == step[idx]


@pytest.mark.xfail(reason="Need to implement")
class TestPipelineFactory:

    @pytest.mark.xfail(reason="Need to implement")
    def test_create_pipeline_from_registered_steps(self):
        registered_steps = [RegisteredStep(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE)]
        factory = PipelineFactory(steps=registered_steps)
        pipeline = factory.create()
        assert isinstance(pipeline, Pipeline)
        assert pipeline.steps[0].key == "test_key"

    @pytest.mark.xfail(reason="Need to implement")
    def test_build_converts_registered_steps_to_steps(self):
        registered_steps = [RegisteredStep(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE)]
        factory = PipelineFactory(steps=registered_steps)
        factory._build()
        assert isinstance(factory.steps[0], Step)
        assert factory.steps[0].key == "test_key"

    @pytest.mark.xfail(reason="Need to implement")
    def test_enter_loads_step_registry(self):
        registered_steps = [RegisteredStep(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE)]
        factory = PipelineFactory(steps=registered_steps)
        with factory as f:
            assert f._registry is not None

    @pytest.mark.xfail(reason="Need to implement")
    def test_exit_unloads_step_registry(self):
        registered_steps = [RegisteredStep(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE)]
        factory = PipelineFactory(steps=registered_steps)
        # noinspection PyUnusedLocal
        with factory as f:
            pass
        assert factory._registry is None
