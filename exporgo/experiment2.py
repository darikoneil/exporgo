from functools import singledispatchmethod
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Callable, Iterable, Optional
import json
from ._io import select_directory, verbose_copy
import portalocker
from redis import Redis

from ._color import TERMINAL_FORMATTER
from ._logging import get_timestamp
from ._validators import convert_permitted_types_to_required
from .exceptions import (DuplicateRegistrationError,
                         ExperimentNotRegisteredError,
                         InvalidExperimentTypeError)
from .files import FileSet, FileTree


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Implementation for Constructing Combinatorial Experiment Functionality
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class ExperimentConfig(BaseModel):
    """
    Recipe for defining an experiment
    """
    name: str = Field("Experiment Type", title="Recipe name")
    collection_descriptor: str = Field("data", title="Descriptor for the contents of the experiment")
    file_sets: str | list[str] = Field([], title="List of file sets for organizing experiment")
    analyzer: str | Path | Callable = Field(title="Analyzer for the experiment")


class ExperimentRegistry:
    """
    Registry for storing experiment configurations
    """
    __registry = {}
    __client = Redis(host="localhost", port="6969", db=0)
    __path = Path(__file__).parent.joinpath("experiments.json")

    @classmethod
    def _save_registry(cls) -> None:
        """
        Save the registry to a JSON file
        """
        try:
            with portalocker.Lock(cls.__path, "w") as file:

            with open(cls.__path, "w") as file:
                # noinspection PyTypeChecker
                json.dump({name: experiment.__name__ for name, experiment in cls.__registry.items()}, file, indent=4)
        except IOError as exc:
            print(TERMINAL_FORMATTER(f"\nError saving registry: {exc}\n", "announcement"))

    @classmethod
    def has(cls, name: str) -> bool:
        """
        Check if an experiment configuration is registered
        """
        return name in cls.__registry

    @classmethod
    def get(cls, name: str) -> ExperimentConfig:
        """
        Get an experiment configuration
        """
        if not cls.has(name):
            raise ExperimentNotRegisteredError(name)
        return cls.__registry[name]

    @classmethod
    def register(cls, experiment: ExperimentConfig) -> None:
        """
        Register an experiment configuration
        """
        if experiment.name in cls.__registry:
            raise DuplicateRegistrationError(experiment.name)
        cls.__registry[experiment.name] = experiment

    @classmethod
    def _load_registry(cls) -> None:
        """
        Load the registry from a JSON file
        """
        try:
            with open(cls.__path, "r") as file:
                fcntl.flock(file, fcntl.LOCK_EX)
                #cls.__registry = {name: getattr(__import__("exporgo.experiment", fromlist=[name]), name) for name in json.load(file)}
                fcntl.flock(file, fcntl.LOCK_UN)
        except (IOError, json.JSONDecodeError) as exc:
            print(TERMINAL_FORMATTER(f"\nError loading registry: {exc}\n", "announcement"))

    @classmethod
    def __enter__(cls):
        with portalocker.RedisLock(cls.__client, cls.__path, timeout=10):


            self._load_registry()
        self._load_registry()
        return self

    @classmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._save_registry()

class ExperimentFactory:
    ...


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
