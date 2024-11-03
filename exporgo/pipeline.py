from pathlib import Path
from typing import Callable, TYPE_CHECKING, Optional
from types import NoneType
from functools import singledispatchmethod


if TYPE_CHECKING:
    from .subject import Subject

from .types import Category, CollectionType, File, Priority, Status, Folder


class AnalysisStep:

    def __init__(self,
                 key: str,
                 call: str | Path | Callable,
                 file_sets: str | list[str] | tuple[str, ...],
                 category: Category,
                 priority: Priority,
                 status: Status):
        self._key = key
        self._call = call
        self._file_sets = file_sets
        self._category = category
        self._priority = priority
        self._status = status

    @property
    def key(self) -> str:
        return self._key

    @property
    def file_sets(self) -> str | CollectionType:
        return self._file_sets

    @property
    def priority(self) -> "Priority":
        return self._priority

    def __call__(self, subject: File or "Subject"):
        self._call(subject)


class Pipeline:
    def __init__(self, steps, priority, status):
        self.steps = steps
        self.priority = priority
        self.status = status

    def analyze(self) -> None:
        ...

    def collect(self, sources: Optional[Folder | CollectionType]) -> None:
        self._collect(sources)

    @singledispatchmethod
    def _collect(self, sources: Optional[Folder | CollectionType]) -> None:
        ...

    @_collect.register(CollectionType)
    def _(self, sources: CollectionType) -> None:
        ...

    @_collect.register(Folder)
    def _(self, sources: Folder) -> None:
        ...

    @_collect.register(type(None))
    def _(self, sources: NoneType) -> None:
        ...
