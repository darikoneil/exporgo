import json
from contextlib import suppress
from functools import singledispatchmethod
from pathlib import Path
from textwrap import indent
from types import GeneratorType, MappingProxyType
from typing import Any, Generator, Optional, Sequence

from portalocker import Lock
from portalocker.constants import LOCK_EX
from portalocker.exceptions import BaseLockException
from pydantic import BaseModel, Field, field_serializer, field_validator

from ._color import TERMINAL_FORMATTER
from ._logging import get_timestamp
from ._tools import check_if_string_set, conditional_dispatch
# noinspection PyProtectedMember
from ._validators import (MODEL_CONFIG, convert_permitted_types_to_required,
                          validate_dumping_with_pydantic,
                          validate_method_with_pydantic)
from .exceptions import (DispatchError, DuplicateRegistrationError,
                         EnumNameValueMismatchError,
                         ExperimentNotRegisteredError)
from .files import FileSet, FileTree
from .pipeline import Pipeline, RegisteredPipeline
from .types import CollectionType, Folder, Priority, Status

__all__ = [
    "Experiment",
    "RegisteredExperiment",
    "ExperimentFactory",
    "ExperimentRegistry",
    "ValidExperiment",
]


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Experiment Model for Serialization & Validation
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class ValidExperiment(BaseModel):
    name: str
    parent_directory: Path
    keys: str | Sequence[str]
    file_tree: Any
    pipeline: Any
    priority: Priority
    meta: dict
    model_config = MODEL_CONFIG

    @field_serializer("priority")
    @classmethod
    def serialize_priority(cls, v: Priority) -> str:
        return f"({v.name}, {v.value})"

    # noinspection PyUnboundLocalVariable
    @field_validator("priority", mode="before", check_fields=True)
    @classmethod
    def validate_priority(cls, v: Any) -> Priority:
        with suppress(ValueError):
            return Priority(v)
        if isinstance(v, str):
            name, value = v[1:-1].split(", ")
            value = int(value)
        elif isinstance(v, tuple):
            name, value = v
        priority = Priority(value)
        try:
            assert priority.name == name
        except AssertionError as exc:
            raise EnumNameValueMismatchError(Priority, name, value) from exc
        return priority


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Experiment Class for Managing File Collection, Access, and Analysis
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
    def keys(self) -> tuple[str , ...]:
        return self._keys

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

    @parent_directory.setter
    def parent_directory(self, parent_directory: Folder) -> None:
        self.remap(parent_directory)

    @conditional_dispatch
    def add_sources(self, *args) -> None:
        raise DispatchError(self.add_sources.__name__, args)

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

    @classmethod
    @validate_method_with_pydantic(ValidExperiment)
    def __deserialize__(cls,
                        name,
                        parent_directory,
                        keys,
                        file_tree,
                        pipeline,
                        priority,
                        **kwargs) -> "Experiment":
        return Experiment(name, parent_directory, keys, file_tree, pipeline, priority, **kwargs)

    @classmethod
    @validate_dumping_with_pydantic(ValidExperiment)
    def __serialize__(cls, self) -> dict:
        return dict(self)  # technically the dict constructor is not necessary, but it's here for clarity.

    def __repr__(self):
        return (f"Experiment("
                f"{self.name=}, "
                f"{self.parent_directory=}, "
                f"{self.keys=}, "
                f"{self.file_tree=}, "
                f"{self.pipeline=}, "
                f"{self.priority=},"
                f"{self.meta=})")

    def __call__(self):
        if self.status == Status.COLLECT:
            # noinspection PyArgumentList
            self.pipeline.collect()
        elif self.status == Status.ANALYZE:
            self.pipeline.analyze()

    # TODO: Experiment needs a __str__ method


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Configuration for Registering Experiments and Registry Class
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class RegisteredExperiment(BaseModel):
    """
    Recipe for defining an experiment
    """
    model_config = MODEL_CONFIG
    key: str = Field(None, title="Unique key for the experiment type in the registry")
    additional_file_sets: str | Sequence[str] = Field(None, title="Additional file sets for organizing experiment")
    pipeline: RegisteredPipeline = Field(None, title="Pipeline for the experiment")
    # sequence does not permit str / bytes, so this works to indicate the list or tuple

    @property
    def file_sets(self) -> set[str]:
        return check_if_string_set(self.additional_file_sets) | self.pipeline.file_sets



class ExperimentRegistry:
    """
    Registry for storing experiment configurations
    """
    __registry = {}
    __path = Path(__file__).parent.joinpath("registered_experiments.json")
    __new_registration = False

    # noinspection DuplicatedCode
    @classmethod
    def _save_registry(cls) -> None:
        """
        Save the registry to a JSON file
        """
        try:
            with Lock(cls.__path, "w", flags=LOCK_EX) as file:
                # noinspection PyTypeChecker
                file.write("{\n")
                for key, experiment in cls.__registry.items():
                    file.write(indent(
                        json.dumps(key)
                        + f": {experiment.model_dump_json(exclude_defaults=True, indent=4)}\n",
                        " " * 4))
                file.write("}\n")
        except FileNotFoundError:
            cls.__path.touch(exist_ok=False)
            cls._save_registry()
        except (IOError, BaseLockException) as exc:
            print(TERMINAL_FORMATTER(f"\nError saving registry: {exc}\n\n", "announcement"))

    @classmethod
    def has(cls, key: str) -> bool:
        """
        Check if an experiment configuration is registered
        """
        return key in cls.__registry

    @classmethod
    def get(cls, key: str) -> "RegisteredExperiment":
        """
        Get an experiment configuration
        """
        if not cls.has(key):
            raise ExperimentNotRegisteredError(key)
        return cls.__registry[key]

    @classmethod
    def pop(cls, key: str) -> "RegisteredExperiment":
        """
        Remove an experiment configuration
        """
        if not cls.has(key):
            raise ExperimentNotRegisteredError(key)
        config = cls.__registry.pop(key)
        cls._save_registry()
        return config

    # noinspection PyNestedDecorators
    @singledispatchmethod
    @classmethod
    def register(cls, experiment: "RegisteredExperiment") -> None:
        """
        Register an experiment configuration
        """
        if experiment.key in cls.__registry:
            raise DuplicateRegistrationError(experiment.key)
        cls.__registry[experiment.key] = experiment
        cls.__new_registration = True

    # noinspection PyNestedDecorators
    @register.register
    @classmethod
    def _(cls, experiment: dict) -> None:
        cls.register(RegisteredExperiment.model_validate(experiment))

    # noinspection PyNestedDecorators
    @register.register(list)
    @register.register(tuple)
    @register.register(set)
    @register.register(GeneratorType)
    @classmethod
    def _(cls, experiment: CollectionType) -> None:
        for config in experiment:
            cls.register(config)

    # noinspection PyNestedDecorators
    @register.register
    @classmethod
    def _(cls, name: str, **kwargs) -> None:
        cls.register(RegisteredExperiment(name=name, **kwargs))

    # noinspection DuplicatedCode
    @classmethod
    def _load_registry(cls) -> None:
        """
        Load the registry from a JSON file
        """
        try:
            with Lock(cls.__path, "r", timeout=10) as file:
                cls.register((RegisteredExperiment.model_validate(config) for _, config in json.load(file).items()))
        except FileNotFoundError:
            cls.__path.touch(exist_ok=False)
            cls._save_registry()
        except (IOError, json.JSONDecodeError) as exc:
            print(TERMINAL_FORMATTER(f"\nError loading registry: {exc}\n\n", "announcement"))

    @classmethod
    def __enter__(cls) -> "ExperimentRegistry":
        cls._load_registry()
        return cls()

    @classmethod
    def __exit__(cls, exc_type, exc_val, exc_tb): # noqa: ANN206
        if cls.__new_registration:
            cls._save_registry()


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Experiment Factory
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


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
