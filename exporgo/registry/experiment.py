from functools import singledispatchmethod
from pathlib import Path
from pydantic import BaseModel, Field
import portalocker
from typing import Callable, Sequence
from types import GeneratorType
import json

from ..priorities import Priority
from .._color import TERMINAL_FORMATTER
from ..exceptions import (DuplicateRegistrationError,
                         ExperimentNotRegisteredError)


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Configuration Schema for Combinatorial Experiment Functionality
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class CollectionConfig(BaseModel):
    name: str = Field(None, title="Recipe name")
    file_sets: str | list[str] | tuple[str] = Field(None, title="List of file sets for organizing experiment")


class AnalysisConfig(BaseModel):
    name: str = Field(None, title="Recipe name")
    call: str | Path | Callable = Field(None, title="Analyzer for the experiment")
    file_sets: str | list[str] | tuple[str] = Field(None, title="List of file sets for organizing experiment")
    priority: Priority = Field(Priority.NORMAL, title="Priority of the analysis")


class ExperimentConfig(BaseModel):
    """
    Recipe for defining an experiment
    """
    name: str = Field(None, title="Recipe name")
    collector: CollectionConfig | Sequence[CollectionConfig] = Field(None, title="Experiment Collection")
    # sequence does not permit str / bytes, so this works to indicate the list or tuple
    analyzer: AnalysisConfig | Sequence[CollectionConfig] = Field(None, title="Experiment Analysis")
    priority: Priority = Field(Priority.NORMAL, title="Priority of the experiment")

    @singledispatchmethod
    def merge(self, experiments: "ExperimentConfig") -> "ExperimentConfig":
        """
        Merge two experiment configurations
        """
        ...


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Implementation of Registry for Experiment Configurations
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


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
                json.dump({name: experiment.model_dump_json(exclude_defaults=True)
                           for name, experiment in cls.__registry.items()},
                          file,
                          indent=4,
                          sort_keys=False
                          )
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
    @register.register(GeneratorType)
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
                cls.register((ExperimentConfig.parse_raw(config) for name, config in json.load(file).items()))
        except (IOError, json.JSONDecodeError) as exc:
            print(TERMINAL_FORMATTER(f"\nError loading registry: {exc}\n\n", "announcement"))

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
