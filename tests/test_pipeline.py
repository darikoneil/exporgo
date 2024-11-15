from types import MappingProxyType
from unittest.mock import MagicMock, patch

import pytest

from exporgo.files import FileTree
from exporgo.pipeline import (Pipeline, PipelineFactory, RegisteredPipeline,
                              ValidPipeline)
from exporgo.step import RegisteredStep, Step, StepRegistry
from exporgo.types import Category, CollectionType, Folder, Status


class TestPipeline:

    def test_initialize_pipeline_with_valid_data(self):
        steps = [Step(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE, status=Status.SOURCE)]
        pipeline = Pipeline(steps=steps, status=Status.SOURCE, sources=MappingProxyType({"files": None}))
        assert pipeline.steps == steps
        assert pipeline.status == Status.SOURCE
        assert pipeline.sources == MappingProxyType({"files": None})

    def test_add_source_updates_sources(self):
        pipeline = Pipeline(steps=[], status=Status.SOURCE, sources=MappingProxyType({"files": None}))
        pipeline.add_source("files", "new_source")
        assert pipeline.sources["files"] == "new_source"

    def test_status_returns_minimum_step_status(self):
        steps = [Step(key="test_key1", call="path/to/file1", file_sets="files1", category=Category.ANALYZE, status=Status.SOURCE),
                 Step(key="test_key2", call="path/to/file2", file_sets="files2", category=Category.ANALYZE, status=Status.TARGET)]
        pipeline = Pipeline(steps=steps, status=Status.SOURCE)
        assert pipeline.status == Status.SOURCE

    def test_collect_updates_step_status_to_analyze(self):
        steps = [Step(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE, status=Status.SOURCE)]
        pipeline = Pipeline(steps=steps, status=Status.SOURCE, sources=MappingProxyType({"files": "source_path"}))
        file_tree = MagicMock()
        pipeline.collect(file_tree)
        assert steps[0].status == Status.ANALYZE

    def test_collect_handles_multiple_file_sets(self):
        steps = [Step(key="test_key", call="path/to/file", file_sets=["files1", "files2"], category=Category.ANALYZE, status=Status.SOURCE)]
        pipeline = Pipeline(steps=steps, status=Status.SOURCE, sources=MappingProxyType({"files1": "source_path1", "files2": "source_path2"}))
        file_tree = MagicMock()
        pipeline.collect(file_tree)
        assert steps[0].status == Status.ANALYZE

    def test_deserialize_creates_pipeline_instance(self):
        pipeline_data = {
            "steps": [Step(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE, status=Status.SOURCE)],
            "status": Status.SOURCE,
            "sources": MappingProxyType({"files": None})
        }
        pipeline = Pipeline.__deserialize__(**pipeline_data)
        assert pipeline.steps == pipeline_data["steps"]
        assert pipeline.status == pipeline_data["status"]
        assert pipeline.sources == pipeline_data["sources"]

    def test_serialize_returns_pipeline_data(self):
        steps = [Step(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE, status=Status.SOURCE)]
        pipeline = Pipeline(steps=steps, status=Status.SOURCE, sources=MappingProxyType({"files": None}))
        serialized_data = Pipeline.__serialize__(pipeline)
        assert serialized_data["steps"] == steps
        assert serialized_data["status"] == Status.SOURCE
        assert serialized_data["sources"] == MappingProxyType({"files": None})

class TestPipelineFactory:

    def test_create_pipeline_from_registered_steps(self):
        registered_steps = [RegisteredStep(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE)]
        factory = PipelineFactory(steps=registered_steps)
        pipeline = factory.create()
        assert isinstance(pipeline, Pipeline)
        assert pipeline.steps[0].key == "test_key"

    def test_build_converts_registered_steps_to_steps(self):
        registered_steps = [RegisteredStep(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE)]
        factory = PipelineFactory(steps=registered_steps)
        factory._build()
        assert isinstance(factory.steps[0], Step)
        assert factory.steps[0].key == "test_key"

    def test_enter_loads_step_registry(self):
        registered_steps = [RegisteredStep(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE)]
        factory = PipelineFactory(steps=registered_steps)
        with factory as f:
            assert f._registry is not None

    def test_exit_unloads_step_registry(self):
        registered_steps = [RegisteredStep(key="test_key", call="path/to/file", file_sets="files", category=Category.ANALYZE)]
        factory = PipelineFactory(steps=registered_steps)
        with factory as f:
            pass
        assert factory._registry is None