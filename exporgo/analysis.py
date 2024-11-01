from pathlib import Path
from typing import Callable
from exporgo.types import CollectionType, Priority


class Analyzer:

    def __init__(self,
                 name: str,
                 call: str | Path | Callable,
                 file_sets: str | list[str] | tuple[str, ...],
                 priority: Priority):
        self._name = name
        self._call = call
        self._file_sets = file_sets
        self._priority = priority

    @property
    def name(self) -> str:
        return self._name

    @property
    def file_sets(self) -> str | CollectionType:
        return self._file_sets

    @property
    def priority(self) -> Priority:
        return self._priority

    def __call__(self, *args, **kwargs):
        ...
