from pathlib import Path

from ._validators import convert_permitted_types_to_required
from .files import FileTree
from ._logging import get_timestamp

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

        #: dict: meta data
        self.meta = kwargs

        self._created = get_timestamp()

    @property
    def base_directory(self) -> Path:
        return self._base_directory

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

    @convert_permitted_types_to_required(permitted=(str, Path), required=Path, pos=1, key="base_directory")
    def remap(self, base_directory: str | Path) -> None:
        self._base_directory = base_directory
        self.file_tree.remap(base_directory)

    def validate(self) -> None:
        self.file_tree.validate()


class ExperimentFactory:
    ...
