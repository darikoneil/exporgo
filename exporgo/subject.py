from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, field_serializer, field_validator

from . import __current_version__
from ._color import TERMINAL_FORMATTER
from ._io import select_directory, select_file
from ._logging import IPythonLogger, ModificationLogger, get_timestamp
from ._validators import (MODEL_CONFIG, convert_permitted_types_to_required,
                          validate_dumping_with_pydantic,
                          validate_method_with_pydantic, validate_priority,
                          validate_status, validate_version)
from .exceptions import DuplicateExperimentError, MissingFilesError
from .experiment import Experiment, ExperimentFactory
from .types import CollectionType, File, Folder, Modification, Priority, Status

__all__ = [
    "Subject",
]


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Subject Model for Serialization and Validation
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class ValidSubject(BaseModel):
    """
    Pydantic model for validating serialization/deserialization of a Subject object.
    """
    #: The name or identifier of the subject.
    name: str
    #: The directory where the subject's data is stored.
    directory: Path
    #: The study the subject is associated with.
    study: Optional[str] = None
    #: The priority of the subject.
    priority: Priority
    #: The status of the subject.
    status: Status
    #: The timestamp associated with the creation of the subject.
    created: str
    #: The last timestamp associated with a modification to the subject.
    last_modified: str
    #: The experiments associated with the subject.
    experiments: dict[str, Experiment | None]
    #: The modifications made to the subject.
    modifications: tuple[Modification, ...]
    #: Metadata associated with the subject.
    meta: dict[str, Any]
    #: The version of the subject.
    version: str
    model_config = MODEL_CONFIG

    @field_serializer("directory")
    @classmethod
    def serialize_directory(cls, v: Path) -> str:
        """
        Serializes the directory field to a string.

        :param v: The directory path to be serialized.

        :return: The serialized directory path as a string.
        """
        return str(v)

    @field_serializer("experiments")
    @classmethod
    def serialize_experiments(cls, v: dict[str, Experiment | None]) -> dict[str, dict]:
        """
        Serializes the experiments field to a dictionary.

        :param v: The experiments dictionary to be serialized.

        :return: The serialized dictionary of experiments
                """
        return {name: experiment.__serialize__(experiment) if experiment is not None else None
                for name, experiment in v.items()}

    @field_serializer("priority")
    @classmethod
    def serialize_priority(cls, v: Priority) -> str:
        """
        Serializes the priority field to a string.

        :param v: The priority to be serialized.

        :return: The serialized priority as a string.
        """
        return f"({v.name}, {v.value})"

    @field_serializer("status")
    @classmethod
    def serialize_status(cls, v: Status) -> str:
        """
        Serializes the status field to a string.

        :param v: The status to be serialized.

        :return: The serialized status as a string.
        """
        return f"({v.name}, {v.value})"

    @field_validator("experiments", mode="before", check_fields=True)
    @classmethod
    def validate_experiments(cls, v: Any) -> Any:
        """
        Validates the experiments field before assignment.

        :param v: The value to be validated.

        :return: The validated dictionary of experiments
        """
        if isinstance(v, dict):
            if any(isinstance(value, Experiment) for value in v.values()):
                return v
            elif any(isinstance(value, dict) for value in v.values()):
                return {key: Experiment.__deserialize__(**value) if value is not None else None
                        for key, value in v.items()}
            elif all((value is None for value in v.values())):
                return v
        return v

    @field_validator("priority", mode="before", check_fields=True)
    @classmethod
    def validate_priority(cls, v: Any) -> Priority | Any:
        """
        Validates the priority field before assignment.

        :param v: The value to be validated.

        :return: The validated priority.
        """
        return validate_priority(v)

    @field_validator("status", mode="before", check_fields=True)
    @classmethod
    def validate_status(cls, v: Any) -> Status | Any:
        """
        Validates the status field before assignment.

        :param v: The value to be validated.

        :return: The validated status.
        """
        return validate_status(v)

    @field_validator("version", mode="after", check_fields=False)
    @classmethod
    def validate_version(cls, v: str) -> Any:
        """
        Validates the version field after assignment.

        :param v: The value to be validated.

        :return: The validated version.
        """
        if v is None:
            return __current_version__
        else:
            validate_version(v)
            return v


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Class for organizing the data of single subjects
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class Subject:
    """
    An organizational class to manage experiments and their associated data.

    :param name: The name or identifier of the subject.

    :param directory: The directory where the subject's data is stored. If not provided, a directory can be selected
        using a file dialog.
    :type directory: :class:`Optional <typing.Optional>`\[:class:`Folder <exporgo.types.Folder>`]

    :param study: The study the subject is associated with.
    :type study: :class:`Optional <typing.Optional>`\[:class:`str`\]

    :param meta: Metadata associated with the subject.
    :type meta: :class:`Optional <typing.Optional>`\[:class:`dict`\]

    :param priority: The priority of the subject
    :type priority: :class:`Priority <exporgo.types.Priority>`

    :param kwargs: Additional keyword arguments to be stored in the subject's metadata dictionary.
    :type kwargs: :class:`Any <typing.Any>`
    """

    @convert_permitted_types_to_required(permitted=(int, Priority),
                                         required=Priority,
                                         pos=5,
                                         key="priority")
    def __init__(self,
                 name: str,
                 directory: Optional[Folder] = None,
                 study: Optional[str] = None,
                 meta: Optional[dict] = None,
                 priority: int | Priority = Priority.NORMAL,
                 **kwargs):

        # first to capture all modifications at creation
        self._modifications = ModificationLogger()

        #: :class:`str`\: The name or identifier of the subject.
        self.name = name

        directory = Path(directory) if directory \
            else select_directory(title="Select folder to contain subject's organized data")
        if name not in directory.name:
            directory = directory.joinpath(name)
        #: :class:`Path <pathlib.Path>`\: The directory where the subject's data is stored.
        self.directory = directory
        if not self.directory.exists():
            Path.mkdir(self.directory)

        #: :class:`str`\: The study the subject is associated with.
        self.study = study

        # determine if auto-starting logging. This is a hidden feature and is taken from kwargs
        start_log = kwargs.pop("start_log", True)
        #: :class:`IPythonLogger <exporgo._logging.IPythonLogger>`\: The logger associated with the subject.
        self.logger = IPythonLogger(self.directory, start_log)

        #: :class:`dict`\: Metadata associated with the subject.
        self.meta = meta if meta else {}
        if kwargs:
            self.meta.update(kwargs)

        #: :class:`Priority <exporgo.types.Priority>`\: The priority of the subject
        self.priority = priority

        #: :class:`str`\: The timestamp associated with the creation of the subject.
        self._created = get_timestamp()

        #: :class:`dict`\[:class:`str`\, :class:`Experiment <exporgo.experiment.Experiment>`\: The experiments associated with the subject.
        self.experiments = {}

        # call this only after all attrs successfully initialized
        self._modifications.append("Instantiated")

        #: :class:`str`\: The version of the subject.
        self._version = __current_version__

    def __str__(self) -> str:
        """
        Returns a string representation of the Subject object.

        :returns: A formatted string representing the subject.

        """
        string_to_print = ""

        string_to_print += TERMINAL_FORMATTER(f"{self.name}\n", "header")
        string_to_print += TERMINAL_FORMATTER("Priority: ", "emphasis")
        string_to_print += f"{self.priority}, {self.priority.name}\n"
        string_to_print += TERMINAL_FORMATTER("Created: ", "emphasis")
        string_to_print += f"{self.created}\n"
        string_to_print += TERMINAL_FORMATTER("Last Modified: ", "emphasis")
        string_to_print += f"{self.last_modified}\n"
        string_to_print += TERMINAL_FORMATTER("Directory: ", "emphasis")
        string_to_print += f"{self.directory}\n"
        string_to_print += TERMINAL_FORMATTER("Study: ", "emphasis")
        string_to_print += f"{self.study}\n"
        string_to_print += TERMINAL_FORMATTER("Meta:\n", "emphasis")
        if not self.meta:
            string_to_print += "\tNo Metadata Defined\n"
        else:
            for key, value in self.meta.items():
                string_to_print += TERMINAL_FORMATTER(f"\t{key}: ", "BLUE")
                string_to_print += f"{value}\n"

        string_to_print += TERMINAL_FORMATTER("Experiments:\n", "emphasis")
        if len(self.contains) == 0:
            string_to_print += "\tNo experiments defined\n"
        else:
            for experiment in self.experiments.values():
                string_to_print + f"{experiment}\n"

        string_to_print += TERMINAL_FORMATTER("Recent Modifications:\n", "modifications")
        for modification in self.modifications[:5]:
            string_to_print += TERMINAL_FORMATTER(f"\t{modification[0]}: ", "BLUE")
            string_to_print += f"{modification[1]}\n"

        return string_to_print

    def save(self) -> None:
        """
        Saves the subject to file.
        """
        self.logger.end()

        with open(self.file, "w") as file:
            yaml.safe_dump(self.__serialize__(),
                           file,
                           default_flow_style=False,
                           sort_keys=False)

        self.logger.start()
        # TODO: FileFormats option

    @property
    def created(self) -> str:
        """
        The timestamp associated with the creation of the subject.

        :Return type: :class:`str`
        :meta read-only-properties:
        """
        return self._created

    @property
    def contains(self) -> tuple[str, ...]:
        """
        The names of the experiments associated with the subject.


        :Return type: :class:`tuple` [:class:`str`\, ...]
        :meta read-only-properties:
        """
        return tuple(self.experiments.keys())

    @property
    def file(self) -> Path:
        """
        The path to the subject's organization file.

        :Return type: :class:`Path <pathlib.Path>`

        :meta read-only-properties:
        """
        return self.directory.joinpath("organization.yaml")

    @property
    def last_modified(self) -> str:
        """
        The last timestamp associated with a modification to the subject.

        :Return type: :class:`str`
        :meta read-only-properties:
        """
        return self.modifications[0][1]

    @property
    def modifications(self) -> tuple[Modification, ...]:
        """
        The modifications made to the subject.

        :Return type: :class:`tuple`\[:class:`Modification <exporgo.types.Modification>`\]
        :meta read-only-properties:
        """
        return tuple(self._modifications)

    @property
    def status(self) -> Status:
        """
        The status of the subject based on the status of its experiments.

        :Return type: :class:`Status <exporgo.types.Status>`
        :meta read-only-properties:
        """
        return min([experiment.status for experiment in self.experiments.values()])\
            if self.experiments else Status.EMPTY

    @property
    def version(self) -> str:
        """
        The version of exporgo

        :Return type: :class:`str`
        :meta read-only-properties:
        """
        return self._version

    @classmethod
    def load(cls, file: Optional[File] = None) -> "Subject":
        """
        Loads a subject from its organization file.

        A file can be selected using a file dialog if no file is provided. Upon loading, the subject's logger is
        started and indexed files for each experiment are validated.

        :param file: The path to the subject's organization file.
        :type file: :class:`Optional <typing.Optional>`\[:class:`File <exporgo.types.File>`]

        :returns: The loaded subject.
        :rtype: :class:`Subject <exporgo.subject.Subject>`

        :raises FileNotFoundError: If the file does not exist.

        :meta class-method:
        """
        file = file if file else select_file(title="Select organization file")
        if not file.is_file():
            file = file.joinpath("organization.json")
        with open(file, "r") as file:
            _dict = yaml.safe_load(file)
        return cls.__deserialize__(_dict)

    # noinspection PyUnusedLocal
    @classmethod
    @validate_method_with_pydantic(ValidSubject)
    def __deserialize__(cls,
                        name: str,
                        status: Status,
                        priority: Priority,
                        created: str,
                        last_modified: str,
                        directory: Path,
                        study: Optional[str],
                        meta: dict,
                        experiments: dict,
                        modifications: list,
                        version: str,
                        ) -> "Subject":
        """
        Deserializes the subject from a dictionary representation. The keys of the dictionary are sent to this method
        as a parameter, and the method returns a Subject object. The deserialization process is validated using the
        ValidSubject Pydantic model.


        :param name: The name or identifier of the subject.

        :param status: The status of the subject.

        :param priority: The priority of the subject.

        :param created: The timestamp associated with the creation of the subject.

        :param last_modified: The last timestamp associated with a modification to the subject.

        :param directory: The directory where the subject's data is stored.

        :param study: The study the subject is associated with.

        :param meta: The metadata associated with the subject.

        :param experiments: The experiments associated with the subject.

        :param modifications: The modifications made to the subject.

        :param version: The version of the subject.

        :return: The deserialized subject.
        """
        # status, last_modified, version are not used
        subject = cls(name, directory, study, meta, priority, start_log=False)
        for name, experiment in experiments.items():
            subject.experiments[name] = experiment
        subject._created = created
        subject._modifications = ModificationLogger(modifications)
        subject.logger.start()
        return subject

    @classmethod
    @validate_dumping_with_pydantic(ValidSubject)
    def __serialize__(cls, self: "Subject") -> dict:
        """
        Serializes the subject for saving to file. The subject (self) is sent to this method as a parameter, and
        the method returns a dictionary representation of the subject. The serialization process is validated using
        the ValidSubject Pydantic model.

        :param self: The subject to be serialized.

        :return: Serialized subject.
        """
        # noinspection PyTypeChecker
        return dict(self)

    def create_experiment(self,
                          name: str,
                          keys: str | CollectionType,
                          priority: Optional[Priority] = None,
                          **kwargs) -> None:
        """
        Creates an experiment associated with the subject.

        :param name: The name of the experiment.

        :param keys: The experiment registry keys used to construct the experiment
        :type keys: :class:`str`\ | :class:`CollectionType`\[:class:`str`\]

        :param priority: Override the priority of the experiment.
        :type priority: :class:`Optional <typing.Optional>`\[:class:`Priority <exporgo.types.Priority>`\]

        :param kwargs: Additional keyword arguments to be stored in the experiment's metadata dictionary.
        :type kwargs: :class:`Any <typing.Any>`

        """
        if name in self.contains:
            raise DuplicateExperimentError(name)

        with ExperimentFactory(name, self.directory) as factory:
            self.experiments[name] = factory(keys, priority, **kwargs)

        self.record(name)

    def record(self, info: str = None) -> None:
        """
        Records a modification to the subject.

        :param info: Information about the modification, defaults to None.
        :type info: :class:`Optional <typing.Optional>`\[:class:`str`\]
        """
        self._modifications.appendleft(info)

    def index(self) -> None:
        """
         Indexes all experiments associated with the subject.
         """
        for experiment in self.experiments.values():
            experiment.index()

    def validate(self) -> None:
        """
        Validates the file tree for all experiments associated with the subject.

        :raises MissingFilesError: If any files are missing in the experiments.
        """
        missing = {}
        for experiment in self.experiments.values():
            try:
                experiment.validate()
            except MissingFilesError as exc:
                missing.update(exc.missing_files)

        if missing:
            raise MissingFilesError(missing)

    def get(self, key: str) -> Any:
        """
        Gets an attribute or experiment by name.

        :param key: The name of the attribute or experiment.

        :returns: The attribute or experiment.
        """
        return getattr(self, key)

    def __repr__(self) -> str:
        """
        Returns a string representation of the Subject object for debugging.

        :returns: A string representation of the subject.
        """
        return "".join([
            f"{self.__class__.__name__}"
            f"({self.name=}, "
            f"{self.directory=}, "
            f"{self.study=}, "
            f"{self.meta=}): "
            f"{self.contains=}, "
            f"{self.exporgo_file=}, "
            f"{self.modifications=}, "
            f"{self._created=}"
        ])

    def __call__(self, name: str) -> Any:
        """
        Allows the Subject object to be called like a function to get an attribute or experiment.

        :param name: The name of the attribute or experiment

        :returns: The attribute or experiment.
        """
        return getattr(self, name)

    def __getattr__(self, item: str) -> Any:
        """
        Gets an attribute or experiment by name.

        :param item: The name of the attribute or experiment.

        :returns: The attribute or experiment.
        """
        if item in self.contains:
            return self.experiments.get(item)
        else:
            return super().__getattribute__(item)

    def __setattr__(self, key: Any, value: Any) -> None:
        """
        Sets an attribute and records the modification.

        :param key: The name of the attribute.

        :param value: The value of the attribute.
        """
        super().__setattr__(key, value)
        self.record(key)

    def __del__(self):
        """
        Destructor to end the logger when the Subject object is deleted.
        """
        if "logger" in vars(self):
            self.logger.end()
            self.logger._IP = None
