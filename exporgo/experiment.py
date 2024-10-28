from functools import singledispatchmethod
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Callable, Iterable, Optional
import json

from ._io import select_directory, verbose_copy

from ._logging import get_timestamp
from ._validators import convert_permitted_types_to_required
from .exceptions import (DuplicateRegistrationError,
                         ExperimentNotRegisteredError,
                         InvalidExperimentTypeError)
from .files import FileSet, FileTree

"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Implementation for Constructing Mix-in Experiment Functionality
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""

#: TODO: Consider changing from mix-in classes to protocol pattern where collect_data and analyze_data are a chain.

#: TODO: Add flags to the Experiment class to indicate if the experiment has been collected or analyzed.


class ExperimentSchema(BaseModel):
    """
    Schema for defining an experiment
    """
    name: str = Field("Experiment Type", title="Schema name")
    collection_descriptor: str = Field("data", title="Descriptor for the contents of the experiment")
    file_sets: str | list[str] = Field([], title="List of file sets for organizing experiment")
    analyzer: str | Path | Callable = Field(title="Analyzer for the experiment")


class Experiment:

    @convert_permitted_types_to_required(permitted=(str, Path), required=Path, pos=2, key="base_directory")
    def __init__(self, name: str, base_directory: str | Path, **kwargs):
        #: str: name of the experiment
        self._name = name

        #: Path: base directory of mouse
        self._base_directory = base_directory

        #: Iterable[str]: iterable of strings that form keys for the experiment registry
        self._mix_ins = kwargs.pop("mix_ins", [])

        #: "FileTree": file tree experimental folders and files
        self.file_tree = FileTree(self._name, base_directory, index=kwargs.pop("index", True))

        #: str: instance date
        self._created = get_timestamp()

        self._collection_progress = 0

        self._analysis_progress = 0

        #: dict: meta data
        self.meta = kwargs

    @property
    def base_directory(self) -> Path:
        return self._base_directory

    @property
    def created(self) -> str:
        return self._created

    @property
    def mix_ins(self) -> Iterable:
        return self._mix_ins

    @property
    def name(self) -> str:
        return self._name

    @staticmethod
    def __name__() -> str:
        return "Experiment"

    def get(self, *args, **kwargs) -> "FileSet":
        return self.file_tree.get(*args, **kwargs)

    def index(self) -> None:
        self.file_tree.index()

    @convert_permitted_types_to_required(permitted=(str, Path), required=Path, pos=1, key="base_directory")
    def remap(self, base_directory: str | Path) -> None:
        self._base_directory = base_directory
        self.file_tree.remap(base_directory)

    def validate(self) -> None:
        self.file_tree.validate()

    def __to_dict__(self):
        return {
            "name": self._name,
            "base_directory": str(self._base_directory),
            "mix_ins": [mix_in.__name__ for mix_in in self._mix_ins],
            "file_tree": self.file_tree.__to_dict__(),
            "instance_date": self._created
        }


class ExperimentRegistry:
    #: dict: registry of experiment mix-ins
    __registry = {}

    @staticmethod
    def type_check(experiment: "Experiment") -> None:
        # noinspection PyTypeChecker
        if not issubclass(experiment, Experiment):
            raise InvalidExperimentTypeError(experiment)

    @classmethod
    def register(cls, alias: Optional[str] = None) -> type["Experiment"]:  #: noqa: ANN206

        def register_experiment(experiment):  # noqa: ANN206, ANN001, ANN201
            nonlocal alias

            cls.type_check(experiment)

            alias = alias if alias is not None else experiment.__name__

            if alias in cls.__registry:
                raise DuplicateRegistrationError(alias)
            else:
                cls.__registry[alias] = experiment
                return experiment

        # noinspection PyTypeChecker
        return register_experiment

    @classmethod
    def has(cls, name: str) -> bool:
        return name in cls.__registry

    @classmethod
    def get(cls, name: str, approximate: bool = False) -> Callable:
        if approximate:
            experiment = next((experiment for key, experiment in cls.__registry.items() if name in key), None)
        else:
            experiment = cls.__registry.get(name)
        if experiment is None:
            raise ExperimentNotRegisteredError(name)
        return experiment


class ExperimentFactory:
    def __init__(self, name: str, base_directory: Path = None):
        #: str: name of experiment
        self._name = name

        #: Path: base directory of mouse
        self.base_directory = base_directory

        #: Iterable[str | "Experiment"]: iterable of mix-ins in string or object form
        self._mix_ins = []

    def object_constructor(self) -> type["Experiment"]:
        params = dict(self.__dict__)
        params.pop("base_directory")
        # noinspection PyTypeChecker
        return type(self._name, tuple(self._mix_ins), params)

    def instance_constructor(self, **kwargs) -> "Experiment":
        experiment_object = self.object_constructor()
        return experiment_object(name=self._name, base_directory=self.base_directory, mix_ins=self._mix_ins, **kwargs)

    @singledispatchmethod
    def add_mix_ins(self, mix_in: Experiment) -> None:
        self._mix_ins.append(mix_in)

    @add_mix_ins.register
    def _ (self, mix_in: str) -> None:
        if not ExperimentRegistry.has(mix_in):
            raise ExperimentNotRegisteredError(mix_in)
        mix_in = ExperimentRegistry.get(mix_in)
        self._mix_ins.append(mix_in)

    @add_mix_ins.register(list)
    @add_mix_ins.register(tuple)
    def _(self, mix_ins: tuple | list) -> None:
        for mix_in in mix_ins:
            self.add_mix_ins(mix_in)
