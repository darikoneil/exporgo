from contextlib import suppress
from functools import singledispatchmethod
from itertools import chain
from pathlib import Path
from shutil import rmtree
from types import GeneratorType, NoneType
from typing import Any, Generator, Iterable, Iterator, Mapping, Optional

from ._validators import convert_permitted_types_to_required
from .exceptions import MissingFilesError
from .types import CollectionType, File, Folder

"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// FileTree Organizer
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class FileTree:
    """
    A file tree that organizes data.

    For implementation concerns it is not an extension of the built-in dictionary type, but it replicates most
    of its built-in methods.
    """

    @convert_permitted_types_to_required(permitted=(Folder, ), required=Path, pos=1, key="directory")
    def __init__(self,
                 directory: Folder,
                 file_sets: Optional[str | CollectionType] = None,
                 populate: bool = True):

        """
        A file tree that organizes experiment data, analyzed results, and figures. For implementation concerns it is not
        an extension of the built-in dictionary type, but it replicates most of its built-in methods.:

        :param directory: directory of file tree
        :type directory: :class:`Folder <exporgo.types.Folder>`

        :param file_sets: file sets to initialize the file tree with
        :type file_sets: :class:`Optional <typing.Optional>`\[:class:`str` |
            :class:`CollectionType <exporgo.types.CollectionType`\]

        :param populate: whether to populate existing filesets in the directory upon initialization
        """
        #: :class:`Folder <exporgo.types.Folder>`: directory of file tree
        self._directory = directory

        self.build(file_sets)

        if populate:
            self.populate()

    @property
    def parent_directory(self) -> Path:
        return self._directory.parent

    @property
    def tree_directory(self) -> Path:
        return self._directory

    @property
    def num_files(self) -> int:
        """
        :Getter: Returns the number of files in the file tree
        :Getter Type: :class:`int`
        :Setter: This property cannot be set
        """
        return sum(len(file_set.files) for file_set in self.values())

    @property
    def num_folders(self) -> int:
        """
        :Getter: Returns the number of folders in the file tree
        :Getter Type: :class:`int`
        :Setter: This property cannot be set
        """
        return sum(len(file_set.folders) for file_set in self.values()) + len(self)

    @classmethod
    def __from_dict__(cls, _dict: dict) -> "FileTree":
        file_tree = cls(_dict.pop("name"), _dict.pop("directory"), index=False)
        for value in _dict.get("file_sets").values():
            name = value.get("name")
            value["directory"] = Path(value.get("directory")).parent
            setattr(file_tree, name, FileSet.__from_dict__(value))
        return file_tree

    def add(self, key: str, index: bool = True) -> None:
        """
        Adds a file set to the file tree

        :param key: key for this file set. Should be "folder" not a full path or literal

        :param index: Whether to index the file set upon creation
        """
        setattr(self, key, FileSet(key, self.tree_directory, index))

    def clear(self, delete: bool = False) -> None:
        """
        Clears the Filetree of all filesets.

        :param delete: Whether to delete the filesets from the file system when cleared
        """
        if delete:
            self._delete(self.keys())

        with suppress(IndexError):
            while True:
                self.popitem()

    def get(self, key: str) -> "FileSet":
        """
        :param key: key of specific file set

        :returns: The file set associated with some key

        :rtype: :class:`FileSet <exporgo.files.FileSet>`
        """
        try:
            return self.__getattribute__(key)
        except AttributeError as exc:
            raise KeyError(f"{key} not in filetree") from exc

    def find(self, identifier: str) -> Generator[Path, None, None]:
        """
        Returns all files that match some identifier

        :param identifier: String identified to match

        :rtype: :class:`Generator <typing.Generator>`\[:class:`Path`\, :class:`None`\, :class:`None`\]
        """
        return (file for file_set in self.values() for file in file_set.find(identifier))

    def items(self) -> Generator[tuple[str, "FileSet"], None, None]:
        """
        Collects the key-value pairs of the filetree

        :return: Key-value pairs of the filetree

        :rtype: :class:`Generator <typing.Generator>`\[:class:`tuple`\[:class:`str`\, :class:`FileSet`\]\,
        """
        return ((key, value) for key, value in vars(self).items() if isinstance(value, FileSet))

    def iter(self) -> Iterator[str]:
        """

        :returns: Iterator over the filesets keys in the filetree

        :rtype: :class:`Iterator <typing.Iterator>`

        """
        return iter(self.keys())

    def keys(self) -> Generator[str, None, None]:
        """
        Collects the keys (filesets) of the file tree

        :return: A generator that returns the keys (filesets) of the file tree

        :rtype: :class:`Generator <typing.Generator>`\[:class:`str`\, :class:`None`\, :class:`None`\]
        """
        return (key for key, _ in self.items())  # items call guarantees filesets only

    def pop(self, key: str) -> "FileSet":
        """
        Remove and return a fileset from the filetree

        :param key: key of fileset to remove

        :return: Fileset removed from the filetree

        :rtype: :class:`FileSet <exporgo.files.FileSet>`

        :raise: KeyError if the fileset is not in the filetree
        """
        if key in self.keys():  # noqa: SIM118
            return vars(self).pop(key)
        else:
            raise KeyError(f"{key} not in filetree")

    def popitem(self) -> "FileSet":
        """
        Remove and return a fileset from the filetree. LIFO order guarantee.

        :raise: IndexError if the filetree is empty

        """
        key = list(self.keys())[-1]
        return self.pop(key)

    def populate(self) -> None:
        """
        Populates the file tree with pre-existing or missing file sets in the directory
        """
        for file_set in (file_set for file_set in self.tree_directory.glob("*") if file_set is not file_set.is_file()):
            self.add(file_set.stem) if (file_set not in self.values()) else None

    def index(self) -> None:
        """
        Indexes the files and folders in the file tree
        """
        for file_set in self.values():
            file_set.index()

    @convert_permitted_types_to_required(permitted=(Folder, ), required=Path, pos=1, key="parent_directory")
    def remap(self, parent_directory: str | Path) -> None:
        """
        Remap the fileset to a new location after moving the folder

        :param parent_directory: base directory of mouse
        """
        self._directory = parent_directory.joinpath(self.tree_directory.name)
        for key in self.keys():
            self.get(key).remap(self.tree_directory)

    def validate(self) -> None:
        """
        Validates that the existing filesets still exist and contain the prescribed files

        :raises MissingFilesError: If any files or folders are missing
        """
        missing = {}
        for value in self.values():
            try:
                value.validate()
            except MissingFilesError as exc:
                missing.update(exc.missing_files)
        if missing:
            raise MissingFilesError(missing)

    def values(self) -> Generator["FileSet", None, None]:
        """
        Collects the filesets of the file tree

        :return: Filesets of the FileTree

        :rtype: :class:`Generator <typing.Generator>`\[:class:`FileSet <exporgo.files.FileSet>`\,
            :class:`None`\, :class:`None`\]

        """
        return (value for _, value in self.items())    # items call guarantees filesets only

    @parent_directory.setter
    @convert_permitted_types_to_required(permitted=(Folder, ), required=Path, pos=0, key="directory")
    def parent_directory(self, directory: Folder) -> None:
        self.remap(directory)

    # noinspection PyUnusedLocal
    @singledispatchmethod
    def build(self, file_sets) -> None:
        """
        Builds the file-tree by initializing any file sets that do not yet exist
        """
        ...

    # noinspection PyUnusedLocal
    @build.register(type(None))
    def _(self, file_sets: NoneType) -> None:  # noqa: U100
        for file_set in self.values():
            if not (directory := file_set.directory).exists():
                directory.mkdir()

    @build.register(list)
    @build.register(tuple)
    @build.register(set)
    @build.register(GeneratorType)
    def _(self, file_sets: CollectionType) -> None:
        for file_set in file_sets:
            self.add(file_set, index=False)
        self.build(None)

    @build.register
    def _(self, file_sets: str) -> None:
        self.add(file_sets, index=False)
        self.build(None)

    @singledispatchmethod
    def _delete(self, key: tuple[str] | list[str] | Generator[str, None, None] | Iterator[str]) -> None:
        """
        Deletes a fileset from the filetree

        :param key: key of fileset to delete
        """
        key = list(key)
        for key_ in key:
            self._delete(key_)

    @_delete.register
    def _(self, key: str) -> None:
        """
        Deletes multiple filesets from the filetree

        :param key: keys of filesets to delete
        """
        value = self.pop(key)
        if isinstance(value, FileSet):
            rmtree(value.directory)

    def __serialize__(self) -> dict:
        return {
            "directory": str(self.tree_directory),
            "file_sets": {key: file_set.__to_dict__() for key, file_set in self.items()}
        }

    def __call__(self, target: Optional[str] = None) -> Path | list[Path]:
        """
        Call the file tree for a specific file or folder and return its Path. If no target provided,
        the file tree directory is returned. If multiple paths meet the target criterion a key error is raised.
        If no path meets the target criterion a file not found error is raised.

        :param target: file or folder name

        """
        if not target:
            return self.tree_directory
        elif len(files := [fileset(target) for fileset in self.values() if fileset(target)]) > 0:
            return files
        else:
            raise FileNotFoundError(f"{target} not found in {self.tree_directory}")

    def __len__(self) -> int:
        """
        Implementation of length magic method.

        :return: Number of file_sets in the filetree

        .. warning:: This method does not return the number of files in the filetree.
            It returns the number of filesets!
        """
        return sum(1 for _ in self.keys())


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// File Tree Contents
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class FileSet:
    """
    Organizing class for a set of files. Contents may be only files or a collection of folders and files.
    This class is useful in managing coherent sets of data like experimental sessions or a calendar day. It offers
    several methods for keeping track of datasets.
    """

    @convert_permitted_types_to_required(permitted=(Folder, ), required=Path, pos=2, key="parent_directory")
    def __init__(self,
                 name: str,
                 parent_directory: Folder,
                 index: bool = True):
        """
        Organizing class for a set of files. Contents may be only files or a collection of folders and files.
        This class is useful in managing coherent sets of data like experimental sessions or a calendar day. It offers
        several methods for keeping track of datasets.

        :param name: Name of file set

        :param parent_directory: Parent directory (filetree)
        :type parent_directory: :class:`Folder <exporgo.types.Folder>`

        :param index: Whether to index the files and folders in the directory upon initialization
        """
        #: :class:`str1\: name of file set
        self._name = name

        #: :class:`Path <pathlib.Path>`\: File set directory
        self.directory = parent_directory.joinpath(name)

        #: :class:`FileMap <exporgo.files.FileMap>`\: Files cache
        self._files = DictWithDuplicates()  # files cache

        #: :class:`FileMap <exporgo.files.FileMap>`\: Folders cache
        self._folders = DictWithDuplicates()  # folders cache

        if index:

            self.index()

    @property
    def name(self) -> str:
        """
        Name of the file set

        :Return Type: :class:`str`

        :meta read-only-properties:
        """
        return self._name

    @property
    def files(self) -> "DictWithDuplicates":
        """
        The files in the file set (cached)

        :Return Type: :class:`DictWithDuplicates <exporgo.files.DictWithDuplicates>`

        :meta read-only-properties:
        """
        return self._files

    @property
    def folders(self) -> "DictWithDuplicates":
        """
        Folders in the file set (cached)

        :Return Type: :class:`DictWithDuplicates <exporgo.files.DictWithDuplicates>`

        :meta read-only-properties:
        """
        return self._folders

    @classmethod
    def __from_dict__(cls, data: dict) -> "FileSet":
        file_set = cls(data.pop("name"), data.pop("directory"), index=False)
        file_set._files = DictWithDuplicates(data.pop("files"))
        file_set._folders = DictWithDuplicates(data.pop("folders"))
        return file_set

    def find(self, identifier: str) -> Generator[Path, None, None]:
        """
        Returns all files that match some identifier

        :param identifier: String identified to match

        :rtype: :class:`list`\[:class:`Path <pathlib.Path>`\]

        """
        return (file for file in self.files.values() if file.match(identifier))

    def index(self) -> None:
        """
        Indexes the files and folders in the file set
        """
        self._files = DictWithDuplicates()
        self._folders = DictWithDuplicates()
        # noinspection PyUnresolvedReferences
        self._files.update(((file.stem, file) for file in self.directory.rglob("*") if file.is_file()))
        self._folders.update(((folder.stem, folder) for folder in self.directory.rglob("*") if not folder.is_file()))

    @convert_permitted_types_to_required(permitted=(Folder, ), required=Path, pos=1, key="parent_directory")
    def remap(self, parent_directory: Folder) -> None:
        """
        Remaps all files and folders in the file set following a change in the parent directory or parent file tree

        :param parent_directory: Parent directory
        :type parent_directory: :class:`Folder <exporgo.types.Folder>`
        """
        self.directory = parent_directory.joinpath(self._name)
        self.index()

    def validate(self) -> None:
        """
        Validates all files and folders in cache still exist

        :raises MissingFilesError: If any files or folders are missing
        """
        missing = {name: location for name, location in self.files.items() if not location.exists()}
        if missing:
            raise MissingFilesError(missing)

    def __to_dict__(self) -> dict:
        return {
            "name": self._name,
            "directory": str(self.directory),
            "files": {name: str(location) for name, location in self.files.items()},
            "folders": {name: str(location) for name, location in self.folders.items()}
        }

    def __call__(self, target: Optional[str] = None) -> Path:
        """
        Call the fileset using a specific target file or folder name and return the associated path. If no target is provided,
        the directory path is returned

        :param target: file or folder name
        :type target: :class:`Optional <typing.Optional>`\[:class:`str`\]

        :type target: :class:`Optional <typing.Optional>`\[:class:`str`\]

        :return: Path of target file or folder

        :raises FileNotFoundError: If the target file or folder is not found
        """
        if not target:
            return self.directory
        elif (location := (self.files.get(target) or self.folders.get(target))) is not None:
            return location
        else:
            raise FileNotFoundError(f"{target} not found in {self.directory}")

    def __eq__(self, other: Any) -> bool:
        """
        Implementation of equality magic method

        :param other: other object to compare to

        :return: Whether the fileset is equal to another object
        """
        return isinstance(other, FileSet) and self.directory == other.directory


class DictWithDuplicates(dict):
    """
    Dictionary extension that appends an integer to duplicate keys before storing as a new key-value pair
    rather than overwriting the existing key-value pair.
    """

    def update(self, __m: Optional[Iterable | Generator[Iterable, None, None]] = None, **kwargs) -> None:
        """
        Updates the dictionary
        """
        if isinstance(__m, Mapping):
            # even though all mappings are iterable, not all iterables have the items method
            items = __m.items()
        elif isinstance(__m, Iterable):
            items = __m
        else:
            items = kwargs.items()

        if __m is not None:
            items = chain(items, kwargs.items())

        for key, value in items:
            self.__setitem__(key, value)

    @convert_permitted_types_to_required(permitted=(File, Folder), required=Path, pos=2, key="value")
    def __setitem__(self, key: str, value: File | Folder) -> None:
        """
        Implementation of setitem magic method. Appends an integer to duplicate keys before storing as a new key-value
        pair. Appends a zero-padded integer to the key to avoid overwriting existing key-value pairs. Maximum number of
        duplicates is 999.

        :param key: key of the dictionary

        :param value: value of the dictionary
        :type value: :class:`File <exporgo.types.File>` | :class:`Folder <exporgo.types.Folder>`
        """
        idx = 0
        while (key := f"{key}_{idx:03}") in self:
            idx += 1

        super().__setitem__(key, value)
