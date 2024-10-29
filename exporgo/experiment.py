from functools import singledispatchmethod
from pathlib import Path
from polars import exclude
from pydantic import BaseModel, Field
import portalocker
from typing import Callable, Iterable, Optional, Generator
from types import GeneratorType
import json
from ._io import select_directory, verbose_copy

from ._color import TERMINAL_FORMATTER
from ._logging import get_timestamp
from ._validators import convert_permitted_types_to_required
from .exceptions import (DuplicateRegistrationError,
                         ExperimentNotRegisteredError,
                         InvalidExperimentTypeError)
from .files import FileSet, FileTree


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Combinatorial Experiment Factory & Functionality
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""

class Experiment:
    @convert_permitted_types_to_required(permitted=(str, Path), required=Path, pos=2, key="base_directory")
    def __init__(self, name: str, base_directory: str | Path, **kwargs):
        #: str: name of the experiment
        self._name = name

        #: Path: base directory of mouse
        self._base_directory = base_directory

        #: "FileTree": file tree experimental folders and files
        self.file_tree = FileTree(self._name, base_directory, index=kwargs.pop("index", True))

        #: str: instance date
        self._created = get_timestamp()

        self._collection_progress = 0

        self._analysis_progress = 0

        #: dict: meta data
        self.meta = kwargs

class ExperimentFactory:
    ...
