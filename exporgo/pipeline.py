from functools import singledispatchmethod
from os import PathLike
from pathlib import Path
from types import GeneratorType, MappingProxyType, NoneType
from typing import Generator, Optional, Sequence

from pydantic import BaseModel, Field

from ._io import select_directory, verbose_copy
from ._tools import check_if_string_set, unique_generator
from ._validators import MODEL_CONFIG
from .files import FileTree
from .step import RegisteredStep, Step
from .types import Category, CollectionType, Folder, Status


class ValidPipeline(BaseModel):
    ...


class Pipeline:
    def __init__(self,
                 steps: Step | CollectionType,
                 status: Status):
        self.steps = steps
        self._status = status
        self._sources = {file_set: None for file_set in self.file_sets}
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
    def _collect(self, sources: Optional[Folder | CollectionType]) -> None:
        ...

    @_collect.register(list)
    @_collect.register(tuple)
    @_collect.register(set)
    @_collect.register(GeneratorType)
    def _(self, sources: CollectionType, destination: Path, name: str) -> None:
        for source in sources:
            self._collect(source, destination, name)

    @_collect.register(str)
    @_collect.register(Path)
    @_collect.register(PathLike)
    def _(self, sources: Folder, destination: Path, name: str) -> None:
        verbose_copy(sources, destination, name)

    # noinspection PyUnusedLocal
    @_collect.register(type(None))
    def _(self, sources: NoneType, destination: Path, name: str) -> None:
        source = select_directory(title=f"Select the source directory for {name}")
        verbose_copy(source, destination, name)

    @classmethod
    def __deserialize__(cls, data: dict) -> "Pipeline":
        return Pipeline(
            Step(key="step_0",
                 call=lambda x: print(f"Step 0: {x=}"),
                 file_sets="data",
                 category=Category.ANALYZE,
                 status=Status.SOURCE), Status.SOURCE)

    def __serialize__(self) -> dict:
        return {
            "steps": self.steps,
            "status": self.status,
            "sources": dict(self.sources),
        }


class RegisteredPipeline(BaseModel):
    steps: RegisteredStep | Sequence[RegisteredStep] = Field(None, title="Sequence of steps in the pipeline")
    model_config = MODEL_CONFIG

    @property
    def file_sets(self) -> set[str]:
        return {file_set for step in self.steps for file_set in check_if_string_set(step.file_sets)}
