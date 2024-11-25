from functools import singledispatchmethod
from os import PathLike
from pathlib import Path
from types import GeneratorType, MappingProxyType, NoneType
from typing import Any, Generator, Mapping, Optional, Sequence

from pydantic import BaseModel, field_serializer, field_validator

from .files import FileTree
from .io import select_directory, verbose_copy
# noinspection PyUnresolvedReferences
from .step import RegisteredStep, Step, StepRegistry
from .tools import check_if_string_set, unique_generator
from .types import CollectionType, Folder, Status
from .validators import (MODEL_CONFIG, validate_dumping_with_pydantic,
                         validate_method_with_pydantic, validate_status)

__all__ = [
    "Pipeline",
    "PipelineFactory",
    "RegisteredPipeline",
    "ValidPipeline",
]


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Pipeline Model for Serialization and Validation
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class ValidPipeline(BaseModel):
    steps: Step | Sequence[Step] | None
    status: Status
    sources: MappingProxyType[str, Folder | CollectionType | None]
    model_config = MODEL_CONFIG

    @field_serializer("sources", check_fields=True)
    @classmethod
    def serialize_sources(cls, v: MappingProxyType[str, Folder | CollectionType | None]) -> dict | None:
        return {file_set: cls._inner_serialize_source(source) for file_set, source in v.items()}

    @singledispatchmethod
    @classmethod
    def _inner_serialize_source(cls, source):
        return str(source)

    @_inner_serialize_source.register(str)
    @_inner_serialize_source.register(Path)
    @_inner_serialize_source.register(PathLike)
    @classmethod
    def _(cls, source: Folder):
        return str(source)

    @_inner_serialize_source.register(list)
    @_inner_serialize_source.register(tuple)
    @_inner_serialize_source.register(set)
    @_inner_serialize_source.register(GeneratorType)
    @classmethod
    def _(cls, source):
        return [cls._inner_serialize_source(s) for s in source]

    # noinspection PyUnusedLocal
    @_inner_serialize_source.register(type(None))
    @classmethod
    def _(cls, source: NoneType):
        return None

    @field_serializer("status")
    @classmethod
    def serialize_status(cls, v: Status) -> str:
        return f"({v.name}, {v.value})"

    @field_serializer("steps", check_fields=True)
    @classmethod
    def serialize_steps(cls, v: Step | Sequence[Step] | None) -> dict | list | None:
        if isinstance(v, Step):
            return v.__serialize__(v)
        elif isinstance(v, (list | tuple)):
            return [step.__serialize__(step) for step in v]
        else:
            return v

    @field_validator("sources", mode="before", check_fields=True)
    @classmethod
    def validate_sources(cls, v: Any) \
            -> MappingProxyType[str, Folder | CollectionType | None]:
        if isinstance(v, dict):
            return MappingProxyType(v)
        elif isinstance(v, MappingProxyType):
            return v
        else:
            return v

    @field_validator("status", mode="before", check_fields=True)
    @classmethod
    def validate_status(cls, v: Any) -> Status | Any:
        return validate_status(v)

    @field_validator("steps", mode="before", check_fields=True)
    @classmethod
    def validate_steps(cls, v: Any) -> Step | Sequence[Step] | None:
        if isinstance(v, (list, tuple)):
            steps = []
            for step in v:
                if not isinstance(step, Step) and isinstance(step, dict):
                    steps.append(Step.__deserialize__(**step))
                if isinstance(step, Step):
                    steps.append(step)
            return steps
        elif isinstance(v, dict):
            return Step.__deserialize__(**v)
        else:
            return v
        # TODO: FIX ME, I don't always return a Step or Sequence[Step]


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Pipeline Class
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class Pipeline:
    def __init__(self,
                 steps: Step | CollectionType,
                 status: Status,
                 sources: Optional[Mapping[str, Folder | CollectionType | None]] = None) -> None:
        self.steps = steps
        self._status = status
        self._sources = dict(sources) if sources else dict.fromkeys(self.file_sets, None)
        # TODO: This will fail, I  will need to fix this
        self._collected = set()

    @property
    def file_sets(self) -> Generator[str, None, None]:
        return unique_generator(file_set for step in self.steps for file_set in check_if_string_set(step.file_sets))

    @property
    def sources(self) -> MappingProxyType[str, Folder | CollectionType | NoneType]:
        return MappingProxyType(self._sources)

    @property
    def status(self) -> Status:
        return min(step.status for step in self.steps) if len(self.steps) > 0 else Status.EMPTY

    def add_source(self,
                   file_set: str,
                   source: Folder | CollectionType | None) -> None:
        self._sources[file_set] = source

    def analyze(self) -> None:
        ...

    def collect(self, file_tree: FileTree) -> None:
        for step in self.steps:
            if step.status == Status.SOURCE or Status.COLLECT:
                for file_set_name in step.file_sets if not isinstance(step.file_sets, str) else [step.file_sets, ]:
                    if file_set_name not in self._collected:
                        destination = file_tree.get(file_set_name)(target=None)
                        sources = self.sources.get(file_set_name)
                        self._collect(sources, destination, file_set_name)
                        self._collected.add(file_set_name)
                step.status = Status.ANALYZE
        file_tree.index()

    @singledispatchmethod
    def _collect(self, sources: Optional[Folder | CollectionType]) -> None:  # noqa: CCE001
        ...

    @_collect.register(list)
    @_collect.register(tuple)
    @_collect.register(set)
    @_collect.register(GeneratorType)
    def _(self, sources: CollectionType, destination: Path, name: str) -> None:  # noqa: CCE001
        for source in sources:
            self._collect(source, destination, name)

    @_collect.register(str)
    @_collect.register(Path)
    @_collect.register(PathLike)
    def _(self, sources: Folder, destination: Path, name: str) -> None:  # noqa: CCE001
        verbose_copy(sources, destination, name)

    # noinspection PyUnusedLocal
    @_collect.register(type(None))
    def _(self, sources: NoneType, destination: Path, name: str) -> None:  # noqa: CCE001, U100
        source = select_directory(title=f"Select the source directory for {name}")
        verbose_copy(source, destination, name)

    @classmethod
    @validate_method_with_pydantic(ValidPipeline)
    def __deserialize__(cls,
                        steps: Step | Sequence[Step] | None,
                        status: Status,
                        sources: MappingProxyType[str, Folder | CollectionType | None]) -> "Pipeline":
        return Pipeline(steps, status, sources)

    @classmethod
    @validate_dumping_with_pydantic(ValidPipeline)
    def __serialize__(cls, self: "Pipeline") -> dict:
        # noinspection PyTypeChecker
        return dict(self)


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Pipeline Class for Registration
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class RegisteredPipeline(BaseModel):
    steps: RegisteredStep | Sequence[RegisteredStep] | None
    model_config = MODEL_CONFIG

    @property
    def file_sets(self) -> set[str]:
        if isinstance(self.steps, RegisteredStep):
            return check_if_string_set(self.steps.file_sets)
        if isinstance(self.steps, (list, tuple)):
            return {file_set for step in self.steps for file_set in check_if_string_set(step.file_sets)}

    @field_serializer("steps", check_fields=True)
    @classmethod
    def serialize_steps(cls, v: RegisteredStep | Sequence[RegisteredStep] | None) -> list | Any:
        if isinstance(v, RegisteredStep):
            return [v.key, ]
        elif isinstance(v, (list | tuple)):
            return [step.key for step in v]
        else:
            return v

    @field_validator("steps", mode="before", check_fields=True)
    @classmethod
    def validate_steps(cls, v: Any) \
            -> RegisteredStep | Sequence[RegisteredStep] | None:
        if isinstance(v, RegisteredStep):
            return v
        elif isinstance(v, (list, tuple)):
            steps = []
            for step in v:
                if isinstance(step, RegisteredStep):
                    steps.append(step)
                elif isinstance(step, str):
                    with StepRegistry() as registry:
                        steps.append(registry.get(step))
            return steps
        else:
            return v


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Pipeline Factory
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class PipelineFactory:
    def __init__(self, steps: RegisteredStep | Sequence[RegisteredStep] | None) -> None:
        self.steps = steps
        self._registry = None

    def create(self) -> Pipeline:
        self._build()
        return Pipeline(self.steps, Status.SOURCE)

    def _build(self) -> None:
        self.steps = [Step.__deserialize__(**vars(step)) for step in self.steps] \
            if isinstance(self.steps, (list, tuple)) \
            else Step.__deserialize__(**vars(self.steps))

    def __enter__(self):
        with StepRegistry() as registry:
            self._registry = registry
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # noqa: U100, ANN201, ANN206, ANN001
        self._registry = None
