from pathlib import Path
from typing import Callable

from .subject import Subject
from .types import Category, CollectionType, File, Priority, Status


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
    def priority(self) -> Priority:
        return self._priority

    def __call__(self, subject: File | Subject):
        self._call(subject)


class Pipeline:
    def __init__(self, steps, priority, status):
        self.steps = steps
        self.priority = priority
        self.status = status
