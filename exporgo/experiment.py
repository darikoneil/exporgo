from pathlib import Path
from types import GeneratorType, MappingProxyType
from typing import Generator, Optional

from ._logging import get_timestamp
from functools import singledispatchmethod
from ._tools import conditional_dispatch
from ._validators import convert_permitted_types_to_required
from .files import FileSet, FileTree
from .pipeline import Pipeline
from .registry import ExperimentRegistry, ExperimentConfig
from .types import CollectionType, Folder, Priority, Status

"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Combinatorial Experiment Factory & Functionality
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


# noinspection PyUnresolvedReferences
class Experiment:

    def __init__(self,
                 name: str,
                 parent_directory: Folder,
                 keys: str | CollectionType,
                 file_tree: FileTree,
                 pipeline: Pipeline,
                 priority: Priority = Priority.NORMAL,
                 **kwargs):
        #: :class:`str`\: name of the experiment
        self._name = name

        #: :class:`Folder <exporgo.types.Folder>`\: base directory of subject
        self._parent_directory = parent_directory

        #: :class:`tuple`: experiment registry keys
        self._keys = (keys, ) if isinstance(keys, str) else keys

        #: :class:`FileTree <exporgo.files.FileTree>`\: file tree for the experiment
        self.file_tree = file_tree

        #: :class:`Pipeline <exporgo.pipeline.Pipeline>`\: pipeline for the experiment
        self.pipeline = pipeline

        #: :class:`Priority <exporgo.types.Priority>`\: priority of the experiment
        self.priority = priority

        #: :class:`dict`\: meta data
        self.meta = kwargs

        #: :class:`str`\: timestamp of creation
        self._created = get_timestamp()

    @property
    def parent_directory(self) -> Path:
        """
        Parent directory of the experiment
        
        :Return type: :class:`Path <pathlib.Path>`
        
        :meta read-only-properties:
        """
        return self._parent_directory

    @property
    def experiment_directory(self) -> Path:
        """
        Directory containing the experiment
        
        :Return type: :class:`Path <pathlib.Path>`
        
        :meta read-only-properties:
        """
        return self.parent_directory.joinpath(self.name)

    @property
    def created(self) -> str:
        """
        The timestamp associated with the creation of the experiment.

        :Return type: :class:`str`
        
        :meta read-only-properties:
        """
        return self._created

    @property
    def name(self) -> str:
        """
        The name of the experiment
        
        :Return type: :class:`str`
        
        :meta read-only-properties:
        """
        return self._name

    @property
    def keys(self) -> tuple[str , ...]:
        return self._keys

    @property
    def status(self) -> Status:
        """
        Current status of the experiment
        
        :Return type: :class:`Status <exporgo.types.Status>`
        
        :meta read-only-properties:
        """
        return self.pipeline.status

    @staticmethod
    def __name__() -> str:
        return "Experiment"

    @parent_directory.setter
    def parent_directory(self, parent_directory: Folder) -> None:
        self.remap(parent_directory)

    @conditional_dispatch
    def add_sources(self, *args) -> None:
        ...

    # noinspection PyUnresolvedReferences
    @add_sources.register(lambda *args: len(args) == 2)
    def _(self, sources: dict[str, Folder | CollectionType | None]) -> None:
        for file_set, source in sources.items():
            self.pipeline.add_source(file_set, source)

    @add_sources.register(lambda *args: len(args) == 3)
    def _(self, file_set: str, source: Folder | CollectionType | None) -> None:
        self.pipeline.add_source(file_set, source)

    def analyze(self) -> None:
        self.pipeline.analyze()

    def collect(self) -> None:
        # noinspection PyTypeChecker
        self.pipeline.collect(self.file_tree)

    def find(self, identifier: str) -> Generator[Path, None, None]:
        """
        Find all files that match some identifier

        :param identifier: identifier to match

        :returns: generator of paths
        """
        return self.find(identifier)

    def get(self, key: str) -> FileSet:
        """
        Get the file set associated with the key

        :param key: key associated with the file set

        :returns: a file set
        :rtype: :class:`FileSet <exporgo.files.FileSet>`
        """
        # noinspection PyUnresolvedReferences
        return self.file_tree.get(key)

    def index(self) -> None:
        """
        Index the files and folders in the experiment's directory
        """
        # noinspection PyArgumentList
        self.file_tree.index()

    @convert_permitted_types_to_required(permitted=(Folder, ), required=Path, pos=1, key="parent_directory")
    def remap(self, parent_directory: Folder) -> None:
        """
        Remap the experiment to a new parent directory
        
        :param parent_directory: new parent directory
        :type parent_directory: :class:`Folder <exporgo.types.Folder>`
        """
        self._parent_directory = parent_directory
        # noinspection PyUnresolvedReferences
        self.file_tree.remap(parent_directory)

    @property
    def sources(self) -> MappingProxyType[str, Folder | CollectionType | None]:
        return self.pipeline.sources

    def validate(self) -> None:
        """
        Validate the experiment's file tree
        """
        # noinspection PyUnresolvedReferences
        self.file_tree.validate()

    def __call__(self):
        if self.status == Status.COLLECT:
            # noinspection PyArgumentList
            self.pipeline.collect()
        elif self.status == Status.ANALYZE:
            self.pipeline.analyze()


class ExperimentFactory:

    @convert_permitted_types_to_required(permitted=(Folder, ), required=Path, pos=2, key="parent_directory")
    def __init__(self,
                 name: str,
                 parent_directory: Folder,
                 priority: Optional[Priority],
                 ):
        self.name = name
        self.parent_directory = parent_directory
        self.priority = priority
        self.registry = None

    def __enter__(self):
        with ExperimentRegistry() as self.registry:
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ...
