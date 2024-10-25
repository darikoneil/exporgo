from abc import abstractmethod
from pathlib import Path
from typing import Callable, Iterable, Optional
from functools import singledispatchmethod

from ._logging import get_timestamp
from ._io import select_directory, verbose_copy
from ._validators import convert_permitted_types_to_required
from .files import FileSet, FileTree


class ExperimentRegistry:
    #: dict: registry of experiment mix-ins
    __registry = {}

    @staticmethod
    def type_check(experiment: "Experiment", raise_exception: bool = False) -> bool | None:
        """
        if raise_exception:
            _ = check_protocol(adapter, (Reader, Writer, Trigger), InvalidExperimentError)
            return True
        else:
            return check_protocol(adapter, (Reader, Writer, Trigger))
        # TODO: Refactor
        """
    # TODO: Refactor

    @classmethod
    def register(cls, alias: Optional[str] = None):  # noqa: ANN206
        """
        A decorator to register a constructor for a particular hardware device
        """
        def register_adapter(experiment):  # noqa: ANN206, ANN001, ANN201
            nonlocal alias

            alias = alias if alias is not None else experiment.__name__
            cls.__registry[alias] = experiment
            return experiment

            #if cls.type_check(experiment):
            #    if alias in cls.__registry:
            #        raise KeyError #DuplicateRegistrationError(cls, alias)
            #    else:
            #        cls.__registry[alias] = experiment
            #        return experiment

        return register_adapter
    # TODO: Refactor

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
            raise KeyError #MissingIdentifierError(cls, name)
        return experiment
    #TODO: Refactor


class ExperimentFactory:
    def __init__(self, name: str, base_directory: Path = None):
        #: str: name of experiment
        self._name = name

        #: Path: base directory of mouse
        self.base_directory = base_directory

        #: Iterable[str | "Experiment"]: iterable of mix-ins in string or object form
        self._mix_ins = []

    @singledispatchmethod
    def add_mix_ins(self, mix_ins: Iterable[str | "Experiment"]) -> None:
        for mix_in in mix_ins:
            self.add_mix_ins(mix_in)

    @add_mix_ins.register
    def _(self, mix_in: str):
        if not ExperimentRegistry.has(mix_in):
            raise KeyError
        mix_in = ExperimentRegistry.get(mix_in)
        self._mix_ins.append(mix_in)

    @add_mix_ins.register
    def _(self, mix_in: "Experiment"):
        self._mix_ins.append(mix_in)

    def object_constructor(self) -> type:
        params = dict(self.__dict__)
        params.pop("base_directory")
        return type(self._name, tuple(self._mix_ins), params)
    # TODO: Review

    def instance_constructor(self) -> "Experiment":
        experiment_object = self.object_constructor()
        return experiment_object(name=self._name, base_directory=self.base_directory, mix_ins=self._mix_ins)
    # TODO: Review


class Experiment:

    @convert_permitted_types_to_required(permitted=(str, Path), required=Path, pos=2, key="base_directory")
    def __init__(self, name: str, base_directory: str | Path, **kwargs):
        #: str: name of the experiment
        self._name = name

        #: Path: base directory of mouse
        self._base_directory = base_directory

        #: Iterable[str | "Experiment"]: iterable of mix-ins in string or object form
        self._mix_ins = kwargs.get("mix_ins", [])

        #: "FileTree": file tree experimental folders and files
        self.file_tree = FileTree(self._name, base_directory)

        #: str: instance date
        self._instance_date = get_timestamp()

        self.generate_file_tree()

    @staticmethod
    def __name__() -> str:
        return "Experiment"

    @classmethod
    def __json_construct__(cls: object, self: object) -> None:
        """
        Constructs the experiment from serialized form

        :rtype: Experiment
        """
        """
        factory = ExperimentFactory(name=self._name, base_directory=self._base_directory)
        factory.add_mix_ins([_import_mix_in_string(mix_in) for mix_in in self._mix_ins])
        experiment = factory.instance_constructor()
        for key, value in vars(self).items():
            if key != "_mix_ins":
                setattr(experiment, key, value)
            else:
                setattr(experiment, key, [_import_mix_in_string(mix_in) for mix_in in self._mix_ins])
        return experiment
        """
        ...
    # TODO: Refactor

    @property
    def base_directory(self) -> Path:
        return self._base_directory

    @property
    def mix_ins(self) -> Iterable[str | "Experiment"]:
        return self._mix_ins

    @property
    def name(self) -> str:
        return self._name

    def get(self, *args, **kwargs) -> "FileSet":
        return self.file_tree.get(*args, **kwargs)

    def index(self) -> None:
        self.file_tree.index()

    @convert_permitted_types_to_required(permitted=(str, Path), required=Path, pos=1, key="base_directory")
    def remap(self, base_directory: str| Path) -> None:
        self._base_directory = base_directory
        self.file_tree.remap(base_directory)

    def validate(self) -> None:
        self.file_tree.validate()

    @abstractmethod
    def collect_data(self) -> None:
        ...

    @abstractmethod
    def analyze_data(self) -> None:
        ...

    @abstractmethod
    def generate_class_files(self) -> None:
        ...

    def generate_file_tree(self) -> None:
        self.file_tree.add_path("results")
        self.file_tree.add_path("figures")
        self.generate_class_files()
        self.file_tree.build()
    # TODO: Review

    def __json_encode__(self) -> dict:
        # serial_encoding = {key: (value if key != "_mix_ins" else [str(value_.__name__) for value_ in value])
        #                   for key, value in vars(self).items()}
        #return serial_encoding
        ...
    # TODO: Refactor


@ExperimentRegistry.register()
class GenericExperiment(Experiment):
    def __init__(self, name: str, base_directory: Path, **kwargs):
        super().__init__(name, base_directory, **kwargs)

    def collect_data(self) -> None:
        data_directory = select_directory(title="Select the directory containing the data")
        _ = verbose_copy(data_directory, self.file_tree.get("data")(None), feedback="data")
        self.file_tree.get("data").index()
        super().collect_data()

    def analyze_data(self) -> None:
        raise NotImplementedError("Generic experiments do not have an implementation for the analyze_data method")

    def generate_class_files(self) -> None:
        self.file_tree.add_path("data")
        super().generate_class_files()
