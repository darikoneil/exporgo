from pathlib import Path


from ._logging import get_timestamp
from ._tools import conditional_dispatch
from ._validators import convert_permitted_types_to_required
from .files import FileSet, FileTree
from .pipeline import Pipeline
from .registry import ExperimentRegistry
from .types import CollectionType, Folder, Priority, Status
from typing import Optional, Generator

"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Combinatorial Experiment Factory & Functionality
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


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

        #: :class:`str` | :class:`CollectionType <exporgo.types.CollectionType>`\: experiment registry keys
        self.keys = keys

        #: :class:`FileTree <exporgo.files.FileTree>`\: file tree for the experiment
        self.file_tree = file_tree,

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

    def analyze(self) -> None:
        self.pipeline.analyze()

    def collect(self, sources: Optional[Folder | CollectionType] = None) -> None:
        self.pipeline.collect(sources)

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

    def validate(self) -> None:
        """
        Validate the experiment's file tree
        """
        # noinspection PyUnresolvedReferences
        self.file_tree.validate()

    def __call__(self):
        if self.status == Status.COLLECT:
            self.pipeline.collect()
        elif self.status == Status.ANALYZE:
            self.pipeline.analyze()


class ExperimentFactory:

    @convert_permitted_types_to_required(permitted=(Folder, ), required=Path, pos=2, key="parent_directory")
    def __init__(self,
                 name: str,
                 parent_directory: Folder,
                 ):
        self.name = name
        self.parent_directory = parent_directory
        self.registry = None

    @conditional_dispatch
    def __call__(self, *args):
        ...

    def __enter__(self):
        with ExperimentRegistry() as self.registry:
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ...
