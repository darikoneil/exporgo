from pydantic import BaseModel, Field
from ..options.options import MODEL_CONFIG
from ..types import Priority, Status, Analysis
from typing import Sequence
import json
from functools import singledispatchmethod
from pathlib import Path
from textwrap import indent
from types import GeneratorType
from typing import Callable, Sequence, Optional

from ..types import CollectionType
from portalocker import Lock
from portalocker.constants import LOCK_EX
from portalocker.exceptions import BaseLockException
from pydantic import BaseModel, Field

from .._color import TERMINAL_FORMATTER
from ..exceptions import (DuplicateRegistrationError,
                          ExperimentNotRegisteredError)
from exporgo.options.options import MODEL_CONFIG
from exporgo.types import Priority


class AnalysisConfig(BaseModel):
    model_config = MODEL_CONFIG
    key: str = Field(None, title="Unique key for the analysis type in the registry")
    call: Analysis = Field(None, title="Analyzer for the experiment")
    file_sets: str | list[str] | tuple[str, ...] = Field(None,
                                                         title="Collection of file sets for organizing experiment")
    priority: Priority = Field(Priority.NORMAL, title="Priority of the analysis")
    status: Status = Field(Status.SOURCE, title="Status of the analysis")


class AnalysisRegistry:
    """
    Registry for storing analysis configurations
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
    def get(cls, key: str) -> "ExperimentConfig":
        """
        Get an experiment configuration
        """
        if not cls.has(key):
            raise ExperimentNotRegisteredError(key)
        return cls.__registry[key]

    @classmethod
    def pop(cls, key: str) -> "ExperimentConfig":
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
    def register(cls, experiment: "ExperimentConfig") -> None:
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
        cls.register(ExperimentConfig.model_validate(experiment))

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
    def __exit__(cls, exc_type, exc_val, exc_tb): # noqa: ANN206
        if cls.__new_registration:
            cls._save_registry()


class PipelineConfig(BaseModel):
    steps: AnalysisConfig | Sequence[AnalysisConfig] = Field(None, title="Sequence of analysis steps")
    priority: Priority = Field(Priority.NORMAL, title="Pipeline Priority")
    status: Status = Field(Status.SOURCE, title="Pipeline Status")
    model_config = MODEL_CONFIG


