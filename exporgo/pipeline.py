from functools import singledispatchmethod
from os import PathLike
from pathlib import Path
from types import GeneratorType, MappingProxyType, NoneType
from typing import Any, Generator, Optional, Sequence

from pydantic import BaseModel, field_serializer, field_validator

from ._io import select_directory, verbose_copy
from ._tools import check_if_string_set, unique_generator
from ._validators import (MODEL_CONFIG, validate_dumping_with_pydantic,
                          validate_method_with_pydantic, validate_status)
from .files import FileTree
from .step import RegisteredStep, Step
from .types import CollectionType, Folder, Status

__all__ = [
    "Pipeline",
    "RegisteredPipeline"
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
        return {file_set: str(source) for file_set, source in v.items()}

    @field_serializer("status")
    @classmethod
    def serialize_status(cls, v: Status) -> str:
        return f"({v.name}, {v.value})"

    @field_serializer("steps", check_fields=True)
    @classmethod
    def serialize_steps(cls, v: Step | Sequence[Step] | None) -> dict | list:
        if isinstance(v, Step):
            return v.__serialize__(v)
        else:
            return [step.__serialize__(step) for step in v]

    @field_validator("sources", mode="before", check_fields=True)
    @classmethod
    def validate_sources(cls, v: MappingProxyType[str, Folder | CollectionType | None]) \
            -> MappingProxyType[str, Folder | CollectionType | None]:
        if isinstance(v, dict):
            return MappingProxyType(v)
        elif isinstance(v, MappingProxyType):
            return v

    @field_validator("status", mode="before", check_fields=True)
    @classmethod
    def validate_status(cls, v: Status) -> Status | Any:
        return validate_status(v)

    @field_validator("steps", mode="before", check_fields=True)
    @classmethod
    def validate_steps(cls, v: Step | Sequence[Step] | None) -> Step | Sequence[Step] | None:
        if isinstance(v, (list, tuple)):
            return [Step.__deserialize__(**step) if isinstance(step, dict) else step for step in v if isinstance(step, Step)]
        elif isinstance(v, dict):
            return Step(**v)
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
                 sources: Optional[MappingProxyType[str, Folder | CollectionType | None]] = None) -> None:
        self.steps = steps
        self._status = status
        self._sources = sources if sources else dict.fromkeys(self.file_sets, None)
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
    def _(self, sources: NoneType, destination: Path, name: str) -> None:  # noqa: CCE001
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
        return {file_set for step in self.steps for file_set in check_if_string_set(step.file_sets)}
