from pathlib import Path
from typing import Any, Optional

import yaml

from . import __current_version__
from ._color import TERMINAL_FORMATTER
from ._io import select_directory, select_file
from ._logging import IPythonLogger, ModificationLogger, get_timestamp
from ._validators import validate_version
from .exceptions import DuplicateExperimentError, MissingFilesError
from .experiment import ExperimentFactory
from .types import File, Folder, Modification, Priority, CollectionType

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

    def __init__(self,
                 name: str,
                 directory: Optional[Folder] = None,
                 study: Optional[str] = None,
                 meta: Optional[dict] = None,
                 priority: Priority = Priority.NORMAL,
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
        self.logger = IPythonLogger(self.directory, start_log)

        #: :class:`dict`\: Metadata associated with the subject.
        self.meta = meta if meta else {}
        if kwargs:
            self.meta.update(kwargs)

        #: :class:`Priority <exporgo.types.Priority>`\: The priority of the subject
        self._priority = priority

        self._created = get_timestamp()

        self._experiments = {}

        # call this only after all attrs successfully initialized
        self._modifications.append("Instantiated")

    def __str__(self) -> str:
        """
        Returns a string representation of the Subject object.

        :returns: A formatted string representing the subject.

        """
        string_to_print = ""

        string_to_print += TERMINAL_FORMATTER(f"{self.name}\n", "header")
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
        if len(self.experiments) == 0:
            string_to_print += "\tNo experiments defined\n"
        for name, experiment in self._experiments.items():
            string_to_print += TERMINAL_FORMATTER(f"\t{name}: \n", "BLUE")
            string_to_print += TERMINAL_FORMATTER("\t\tCreated: ", "GREEN")
            string_to_print += f"{experiment.created}\n"
            string_to_print += TERMINAL_FORMATTER("\t\tProperties: ", "GREEN")
            string_to_print += "".join([mix_in.__name__ + ", " for mix_in in experiment.mix_ins])[:-2]
            string_to_print += "\n"
            string_to_print += TERMINAL_FORMATTER("\t\tMeta: \n", "GREEN")
            if not experiment.meta:
                string_to_print += "\t\t\tNo Metadata Defined\n"
            else:
                for key, value in experiment.meta.items():
                    string_to_print += TERMINAL_FORMATTER(f"\t\t\t{key}: ", "ORANGE")
                    string_to_print += f"{value}\n"
            string_to_print += TERMINAL_FORMATTER("\t\tFile Tree: \n", "GREEN")
            for key, file_set in experiment.file_tree.items():
                string_to_print += TERMINAL_FORMATTER(f"\t\t\t{key.capitalize()}: ", "ORANGE")
                string_to_print += f"{len(file_set.files)} Files\n"

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
            yaml.safe_dump(self.__to_dict__(),
                           file,
                           default_flow_style=False,
                           sort_keys=False)

        self.logger.start()

    @property
    def created(self) -> str:
        """
        The timestamp associated with the creation of the subject.

        :Return type: :class:`str`
        :meta read-only-properties:
        """
        return self._created

    @property
    def experiments(self) -> tuple[str, ...]:
        """
        The names of the experiments associated with the subject.


        :Return type: :class:`tuple` [:class:`str`\, ...]
        :meta read-only-properties:
        """
        return tuple(self._experiments.keys())

    @property
    def file(self) -> Path:
        """
        The path to the subject's organization file.

        :Return type: :class:`Path <pathlib.Path>`

        :meta read-only-properties:
        """
        return self.directory.joinpath("organization.json")

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
        return cls.__from_dict__(_dict)

    @classmethod
    def __from_dict__(cls, _dict: dict) -> "Subject":
        """
        Creates a Subject instance from a dictionary.

        :param _dict: The dictionary containing subject data.

        :returns: The created subject.
        :rtype: :class:`Subject <exporgo.subject.Subject>`
        """

        validate_version(_dict.pop("version"))

        subject = cls(
            name=_dict.get("name"),
            directory=_dict.get("directory"),
            study=_dict.get("study"),
            meta=_dict.get("meta"),
            start_log=False
        )

        subject._created = _dict.get("created")
        subject._modifications = ModificationLogger(_dict.get("modifications"))
        subject.logger.start()

        return subject

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
        if name in self.experiments:
            raise DuplicateExperimentError(name)

        with ExperimentFactory(name, self.directory) as factory:
            self._experiments[name] =  factory(keys, priority, **kwargs)

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
        for experiment in self._experiments.values():
            experiment.index()

    def validate(self) -> None:
        """
        Validates the file tree for all experiments associated with the subject.

        :raises MissingFilesError: If any files are missing in the experiments.
        """
        missing = {}
        for experiment in self._experiments.values():
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

    def __to_dict__(self) -> dict[str, Any]:
        """
        Converts the Subject object to a dictionary.

        :returns: The dictionary representation of the subject.

        :rtype: dict[str, Any]
        """
        return {
            "name": self.name,
            "created": self.created,
            "last_modified": self.last_modified,
            "directory": str(self.directory),
            "file": str(self.file),
            "study": self.study,
            "meta": self.meta,
            "experiments": {name: experiment.__to_dict__() for name, experiment in self._experiments.items()},
            "modifications": self.modifications,
            "version": __current_version__,
        }

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
            f"{self.experiments=}, "
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
        if item in self.experiments:
            return self._experiments.get(item)
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
