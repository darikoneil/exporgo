from functools import singledispatchmethod
from pathlib import Path
from pydantic import BaseModel, Field
import portalocker
from typing import Callable, Iterable, Optional
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
    analyzer: str | Path | Callable = Field(lambda *args, **kwargs: None, title="Analyzer for the experiment")


class ExperimentRegistry:
    """
    Registry for storing experiment configurations
    """
    __registry = {}
    __path = Path(__file__).parent.joinpath("registry").joinpath("experiments.json")

    @classmethod
    def _save_registry(cls) -> None:
        """
        Save the registry to a JSON file
        """
        try:
            with portalocker.Lock(cls.__path, "a", timeout=10) as file:
                # noinspection PyTypeChecker
                json.dump({name: experiment.json() for name, experiment in cls.__registry.items()}, file, indent=4)
        except IOError as exc:
            print(TERMINAL_FORMATTER(f"\nError saving registry: {exc}\n", "announcement"))

    @classmethod
    def has(cls, name: str) -> bool:
        """
        Check if an experiment configuration is registered
        """
        return name in cls.__registry

    @classmethod
    def get(cls, name: str) -> "ExperimentConfig":
        """
        Get an experiment configuration
        """
        if not cls.has(name):
            raise ExperimentNotRegisteredError(name)
        return cls.__registry[name]

    @classmethod
    def pop(cls, name: str) -> "ExperimentConfig":
        """
        Remove an experiment configuration
        """
        if not cls.has(name):
            raise ExperimentNotRegisteredError(name)
        config = cls.__registry.pop(name)
        cls._save_registry()
        return config

    # noinspection PyNestedDecorators
    @singledispatchmethod
    @classmethod
    def register(cls, experiment: "ExperimentConfig") -> None:
        """
        Register an experiment configuration
        """
        if experiment.name in cls.__registry:
            raise DuplicateRegistrationError(experiment.name)
        cls.__registry[experiment.name] = experiment

    # noinspection PyNestedDecorators
    @register.register(list)
    @register.register(tuple)
    @classmethod
    def _(cls, experiment: list | tuple) -> None:
        for config in experiment:
            cls.register(config)

    # noinspection PyNestedDecorators
    @register.register
    @classmethod
    def _(cls, name: str, **kwargs) -> None:
        cls.register(ExperimentConfig(name=name, **kwargs))

    @classmethod
    def _load_registry(cls) -> None:
        """
        Load the registry from a JSON file
        """
        try:
            with portalocker.Lock(cls.__path, "r", timeout=10) as file:
                cls.register({name: ExperimentConfig(**config) for name, config in json.load(file).items()})
        except (IOError, json.JSONDecodeError) as exc:
            print(TERMINAL_FORMATTER(f"\nError loading registry: {exc}\n", "announcement"))

    @staticmethod
    def _validate(config: dict) ->"ExperimentConfig":
        """
        Validate an experiment configuration
        """
        return ExperimentConfig(**config)

    @classmethod
    def __enter__(cls):
        cls._load_registry()

    @classmethod
    def __exit__(cls, exc_type, exc_val, exc_tb):
        ...


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
