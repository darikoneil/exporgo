from pathlib import Path

from ._logging import get_timestamp
from ._tools import conditional_dispatch
from ._validators import convert_permitted_types_to_required
from .files import FileSet, FileTree
from .pipeline import Pipeline
from .registry import ExperimentRegistry
from .types import CollectionType, Folder, Priority, Status

"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Combinatorial Experiment Factory & Functionality
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class Experiment:

    def __init__(self,
                 name: str,
                 base_directory: Folder,
                 keys: str | CollectionType,
                 file_tree: FileTree,
                 pipeline: Pipeline,
                 priority: Priority = Priority.NORMAL,
                 **kwargs):
        #: str: name of the experiment
        self._name = name

        #: Folder: base directory of subject
        self._base_directory = base_directory

        #: str | Collection Type: experiment registry keys
        self.keys = keys

        #: FileTree: file tree for the experiment
        self.file_tree = file_tree,

        #: Pipeline: pipeline for the experiment
        self.pipeline = pipeline

        #: Priority: priority of the experiment
        self.priority = priority

        #: dict: meta data
        self.meta = kwargs

        # timestamp of creation
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

    @property
    def status(self) -> Status:
        return self.pipeline.status

    @staticmethod
    def __name__() -> str:
        return "Experiment"

    @base_directory.setter
    def base_directory(self, base_directory: Folder) -> None:
        self.remap(base_directory)

    def get(self, *args, **kwargs) -> FileSet:
        return self.file_tree.get(*args, **kwargs)

    def index(self) -> None:
        self.file_tree.index()

    @convert_permitted_types_to_required(permitted=(Folder, ), required=Path, pos=1, key="base_directory")
    def remap(self, base_directory: Folder) -> None:
        self._base_directory = base_directory
        self.file_tree.remap(base_directory)

    def validate(self) -> None:
        self.file_tree.validate()

    def __call__(self, *args, **kwargs):
        return self.get(*args, **kwargs)



class ExperimentFactory:

    @convert_permitted_types_to_required(permitted=(Folder, ), required=Path, pos=2, key="base_directory")
    def __init__(self,
                 name: str,
                 base_directory: Folder,
                 ):
        self.name = name
        self.base_directory = base_directory
        self.registry = None

    @conditional_dispatch
    def __call__(self, *args):
        ...

    def __enter__(self):
        with ExperimentRegistry() as self.registry:
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ...
