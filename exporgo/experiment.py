from pathlib import Path
from functools import singledispatchmethod, singledispatch
from .registry import AnalysisConfig, ExperimentConfig, ExperimentRegistry
from ._validators import convert_permitted_types_to_required
from .files import FileTree, FileSet
from ._logging import get_timestamp
from typing import Optional
from .registry.options import Priority
from ._tools import conditional_dispatch
from types import GeneratorType
from ._io import verbose_copy, select_directory


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Combinatorial Experiment Factory & Functionality
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""

class Experiment:

    @convert_permitted_types_to_required(permitted=(str, Path), required=Path, pos=2, key="base_directory")
    def __init__(self,
                 name: str,
                 base_directory: str | Path,
                 config: ExperimentConfig,
                 priority: Priority = None,
                 **kwargs):
        #: str: name of the experiment
        self._name = name

        #: Path: base directory of subject
        self._base_directory = base_directory

        self.config = config

        self.priority = config.priority if priority is None else priority

        #: "FileTree": file tree experimental folders and files
        self.file_tree = FileTree(self._name, self._base_directory, index=kwargs.pop("index", True))
        self._generate_file_sets()

        #: dict: meta data
        self.meta = kwargs

        self._created = get_timestamp()

    @property
    def base_directory(self) -> Path:
        return self._base_directory

    @property
    def experiment_directory(self) -> Path:
        return self.base_directory.joinpath(self.name)
    @property
    def created(self) -> str:
        return self._created

    @property
    def name(self) -> str:
        return self._name

    @staticmethod
    def __name__() -> str:
        return "Experiment"

    @base_directory.setter
    def base_directory(self, base_directory: str | Path) -> None:
        self.remap(base_directory)

    def analyze(self) -> bool:
        ...

    # noinspection PyUnusedLocal
    @singledispatchmethod
    def collect(self, path: Optional = None):
        for name, destination in self.file_tree.items():
            source = select_directory(title=f"Select {name} source")
            verbose_copy(source, destination.directory, name)


    @collect.register(str)
    @collect.register(Path)
    def _(self, path: ) -> bool:


    def get(self, *args, **kwargs) -> FileSet:
        return self.file_tree.get(*args, **kwargs)

    def index(self) -> None:
        self.file_tree.index()

    @convert_permitted_types_to_required(permitted=(str, Path), required=Path, pos=1, key="base_directory")
    def remap(self, base_directory: str | Path) -> None:
        self._base_directory = base_directory
        self.file_tree.remap(base_directory)

    def validate(self) -> None:
        self.file_tree.validate()

    def _generate_file_sets(self) -> None:
        for required_file_set in self.config.required_file_sets:
            self.file_tree.add(required_file_set)
        for file_set in self.file_tree.values():
            if not (directory := file_set.directory).exists():
                directory.mkdir()

    def __call__(self, *args, **kwargs):
        return self.get(*args, **kwargs)



class ExperimentFactory:

    def __init__(self,
                 name: str,
                 base_directory: str | Path
                 ):
        self.name = name
        self.base_directory = base_directory
        self.registry = None

    @conditional_dispatch
    def __call__(self, *args):
        ...

    @__call__.register(lambda *args: len(args) == 2 and isinstance(args[1], ExperimentConfig))
    def _(self, *args):
        return Experiment(self.name, self.base_directory)

    def __enter__(self):
        with ExperimentRegistry() as self.registry:
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ...
