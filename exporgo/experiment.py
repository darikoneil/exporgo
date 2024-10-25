from abc import abstractmethod
from pathlib import Path
from typing import Iterable, Optional, Callable

from ._logging import get_timestamp
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

    @classmethod
    def register(cls, alias: Optional[str] = None):  # noqa: ANN206
        """
        A decorator to register a constructor for a particular hardware device
        """
        def register_adapter(experiment):  # noqa: ANN206, ANN001, ANN201
            nonlocal alias

            alias = alias if alias is not None else experiment.__name__
            if cls.type_check(experiment):
                if alias in cls.__registry:
                    raise KeyError #DuplicateRegistrationError(cls, alias)
                else:
                    cls.__registry[alias] = experiment
                    return experiment

        return register_adapter
    # TODO: Refactor

    @classmethod
    def has(cls, name: str) -> bool:
        """
        Check if a experiment mix-in is registered
        """
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


class Experiment:

    @convert_permitted_types_to_required(permitted=(str, Path), required=Path, pos=2, key="base_directory")
    def __init__(self, name: str, base_directory: str | Path, **kwargs):
        """
        Abstract experiment class that collects its methods through mix-ins. These mix-ins add experimental features to
        the object. For example, the imaging mix-in adds methods for collecting imaging data for placement in the
        file tree

        :param name: name of experiment
        :param base_directory: base directory of mouse

        :key mix_ins: an iterable of mix-ins in string or object form
        """
        #: str: name of the experiment
        self._name = name
        #: Path: base directory of mouse
        self._base_directory = base_directory
        #: Iterable: iterable of mix-ins in string or object form
        self._mix_ins = kwargs.get("mix_ins", [])
        #: pd.DataFrame: synchronized experiment data
        self.data = None
        #: dict: file tree experimental folders and files
        self.file_tree = FileTree(self._name, base_directory)
        #: str: instance date
        self._instance_date = get_timestamp()

        self.generate_file_tree()

    @staticmethod
    def __name__() -> str:
        return "Experiment"

    @classmethod
    def __json_construct__(cls: object, self: object) -> "Experiment":
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

    def get(self, *args, **kwargs) -> FileSet:
        return self.file_tree.get(*args, **kwargs)

    def reindex(self) -> None:
        """
        Updates file tree

        :rtype: Experiment
        """
        self.file_tree.index()

    def remap(self, base_directory: Path) -> None:
        """
        Remaps file tree to a new base_directory, allowing us to move our folder without destroying our file tree.

        :param base_directory: base directory of mouse
        :type base_directory: pathlib.Path
        :rtype: Experiment
        """
        self._base_directory = base_directory
        self.file_tree.remap(base_directory)

    def validate(self) -> None:
        self.file_tree.validate()

    @abstractmethod
    def collect_data(self) -> "Experiment":
        """
        Abstract method for collecting experimental data and organizing into the file tree

        :rtype: Experiment
        """
        pass

    @abstractmethod
    def analyze_data(self) -> "Experiment":
        """
        Abstract method for analyzing the data within the file tree

        :rtype: Experiment
        """
        pass

    @abstractmethod
    def generate_class_files(self) -> "Experiment":
        """
        Abstract method for generating any file sets within the file tree that are specific to some mix-in

        :rtype: Experiment
        """
        pass

    def generate_file_tree(self) -> None:
        """
        Method generates the experiment's file tree

        :rtype: Experiment
        """
        self.file_tree.add_path("results")
        self.file_tree.add_path("figures")
        self.generate_class_files()
        self.file_tree.build()

    def __json_encode__(self) -> dict:
        """
        Method encodes the object into a serializable dictionary

        :rtype: dict
        """
        serial_encoding = {key: (value if key != "_mix_ins" else [str(value_.__name__) for value_ in value])
                           for key, value in vars(self).items()}
        return serial_encoding


class ExperimentFactory:
    def __init__(self, name: str, base_directory: Path = None):
        """
        Factory for dynamically creating an experiment using the abstract experiment class and an iterable of mix-ins

        :param name: name of experiment
        :type name: str
        :param base_directory: base directory of mouse
        :type base_directory: pathlib.Path = None
        """
        #: str: name of experiment
        self._name = name
        #: Path: base directory of mouse
        self.base_directory = base_directory
        #: Iterable: iterable of mix-ins in string or object form
        self._mix_ins = []

    def add_mix_ins(self, mix_ins: Iterable) -> None:
        """
        Add mix-ins to the factory to include them when generating the experiment

        :param mix_ins: an iterable of mix-ins in string or object form
        :type mix_ins: Iterable
        :rtype: ExperimentFactory
        """
        """
        for mix_in in mix_ins:
            if isinstance(mix_in, str):
                mix_in = _import_mix_in_string(mix_in)
            self._mix_ins.append(mix_in)
        """
        ...

    def object_constructor(self) -> "Experiment":
        """
        Construct a concrete experiment object using the mix-ins

        :return: A concrete experiment object
        :rtype: Experiment
        """
        params = dict(self.__dict__)
        params.pop("base_directory")
        return type(self._name, tuple(self._mix_ins), params)

    def instance_constructor(self) -> "Experiment":
        """
        Construct an instance of a concrete experiment object using the mix-ins

        :return: An instance of a concrete experiment object
        :rtype: Experiment
        """
        experiment_object = self.object_constructor()
        # noinspection PyCallingNonCallable
        return experiment_object(name=self._name, base_directory=self.base_directory, mix_ins=self._mix_ins)


