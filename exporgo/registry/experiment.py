from functools import singledispatchmethod
from pathlib import Path
from pydantic import BaseModel, Field
from portalocker import Lock
from portalocker.constants import LOCK_EX
from portalocker.exceptions import BaseLockException
from typing import Callable, Sequence
from types import GeneratorType
import json
from textwrap import indent

from .options import MODEL_CONFIG, Priority
from .._color import TERMINAL_FORMATTER
from ..exceptions import (DuplicateRegistrationError,
                         ExperimentNotRegisteredError)


__all__ = [
    "AnalysisConfig",
    "CollectionConfig",
    "ExperimentConfig",
    "ExperimentRegistry"
]


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Configuration Schema for Combinatorial Experiment Functionality
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class CollectionConfig(BaseModel):
    model_config = MODEL_CONFIG
    name: str = Field(None, title="Recipe name")
    file_sets: str | list[str] | tuple[str] = Field(None, title="List of file sets for organizing experiment")


class AnalysisConfig(BaseModel):
    model_config = MODEL_CONFIG
    name: str = Field(None, title="Recipe name")
    call: str | Path | Callable = Field(None, title="Analyzer for the experiment")
    file_sets: str | list[str] | tuple[str] = Field(None, title="List of file sets for organizing experiment")
    priority: Priority = Field(Priority.NORMAL, title="Priority of the analysis")


class ExperimentConfig(BaseModel):
    """
    Recipe for defining an experiment
    """
    model_config = MODEL_CONFIG
    name: str = Field(None, title="Recipe name")
    collector: CollectionConfig | Sequence[CollectionConfig] = Field(None, title="Experiment Collection")
    # sequence does not permit str / bytes, so this works to indicate the list or tuple
    analyzer: AnalysisConfig | Sequence[CollectionConfig] = Field(None, title="Experiment Analysis")
    priority: Priority = Field(Priority.NORMAL, title="Global priority of the experiment")

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
    __path = Path(__file__).parent.joinpath("experiments.json")
    __new_registration = False

    @classmethod
    def _save_registry(cls) -> None:
        """
        Save the registry to a JSON file
        """
        try:
            with Lock(cls.__path, "w", flags=LOCK_EX) as file:
                # noinspection PyTypeChecker
                file.write("{\n")
                for name, experiment in cls.__registry.items():
                    file.write(indent(json.dumps(experiment.name) + f": {experiment.model_dump_json(exclude_defaults=True, indent=4)}\n", " " * 4))
                file.write("}\n")
                #json.dump({name: experiment.model_dump_json(exclude_defaults=True) for name, experiment in cls.__registry.items()}, file, indent=4)
        except FileNotFoundError:
            cls.__path.touch(exist_ok=False)
            cls._save_registry()
        except (IOError, BaseLockException) as exc:
            print(TERMINAL_FORMATTER(f"\nError saving registry: {exc}\n\n", "announcement"))

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
        cls.__new_registration = True

    # noinspection PyNestedDecorators
    @register.register
    @classmethod
    def _(cls, experiment: dict) -> None:
        cls.register(ExperimentConfig.model_validate(experiment))

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
            with Lock(cls.__path, "r", timeout=10) as file:
                cls.register((ExperimentConfig.model_validate(config) for _, config in json.load(file).items()))
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
    def __exit__(cls, exc_type, exc_val, exc_tb):
        if cls.__new_registration:
            cls._save_registry()
