from functools import singledispatchmethod
from os import PathLike
from pathlib import Path
from types import GeneratorType, MappingProxyType, NoneType
from typing import TYPE_CHECKING, Callable, Generator, Optional

if TYPE_CHECKING:
    from .subject import Subject

from ._io import select_directory, verbose_copy
from ._tools import check_if_string_set, unique_generator
from .files import FileTree
from .types import Category, CollectionType, File, Folder, Status


class AnalysisStep:

    def __init__(self,
                 key: str,
                 call: str | Path | Callable,
                 file_sets: str | list[str] | tuple[str, ...],
                 category: Category,
                 status: Status):
        self._key = key
        self._call = call
        self._file_sets = file_sets
        self._category = category
        self.status = status

    @property
    def key(self) -> str:
        return self._key

    @property
    def category(self) -> Category:
        return self._category

    @property
    def file_sets(self) -> str | CollectionType:
        return self._file_sets

    def __call__(self, subject: File or "Subject"):
        self._call(subject)


class Pipeline:
    def __init__(self,
                 steps: AnalysisStep | CollectionType,
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
        return min(step.status for step in self.steps)

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
