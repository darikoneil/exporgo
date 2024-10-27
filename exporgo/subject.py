from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

from . import FileTree
from ._color import TERMINAL_FORMATTER
from ._io import select_directory, select_file
from ._logging import IPythonLogger, ModificationLogger, get_timestamp
from .exceptions import DuplicateExperimentError, MissingFilesError
from .experiment import Experiment, ExperimentFactory


class Subject:

    def __init__(self,
                 name: str,
                 directory: Optional[str | Path] = None,
                 species: Optional[str] = None,
                 study: Optional[str] = None,
                 condition: Optional[str] = None,
                 meta: Optional[dict] = None,
                 **kwargs):

        #: "ModificationLogger": modifications to this object
        self._modifications = ModificationLogger()

        #: str: subject name
        self.name = name

        #: Path: directory to save mouse within; if directory doesn't contain subject name, we ought to add it
        # if directory doesn't exist, create it
        directory = Path(directory) if directory \
            else select_directory(title="Select folder to contain subject's organized data")
        if name not in directory.name:
            directory = directory.joinpath(name)
        self.directory = directory
        if not self.directory.exists():
            Path.mkdir(self.directory)

        # determine if auto-starting logging. This is a hidden feature and is taken from kwargs
        start_log = kwargs.pop("start_log", True)
        #: IPython_logger: logging object
        self.logger = IPythonLogger(self.directory, start_log)

        #: str: species
        self.species = species

        #: str: name of study
        self.study = study

        #: str: condition
        self.condition = condition

        #: dict: meta data
        self.meta = meta if meta else {}
        if kwargs:
            self.meta.update(kwargs)

        #: str: instance date
        self._created = get_timestamp()

        #: dict: experiments
        self._experiments = {}

        # call this only after all attrs successfully initialized
        self._modifications.append("Instantiated")

    def __str__(self) -> str:
        string_to_print = ""

        string_to_print += TERMINAL_FORMATTER(f"{self.name}\n", "header")
        string_to_print += TERMINAL_FORMATTER("Created: ", "emphasis")
        string_to_print += f"{self.created}\n"
        string_to_print += TERMINAL_FORMATTER("Last Modified: ", "emphasis")
        string_to_print += f"{self.last_modified}\n"
        string_to_print += TERMINAL_FORMATTER("Directory: ", "emphasis")
        string_to_print += f"{self.directory}\n"
        string_to_print += TERMINAL_FORMATTER("Species: ", "emphasis")
        string_to_print += f"{self.species}\n"
        string_to_print += TERMINAL_FORMATTER("Study: ", "emphasis")
        string_to_print += f"{self.study}\n"
        string_to_print += TERMINAL_FORMATTER("Condition: ", "emphasis")
        string_to_print += f"{self.condition}\n"

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
        self.logger.end()

        with open(self.file, "w") as file:
            yaml.safe_dump(self.__to_dict__(),
                           file,
                           default_flow_style=False,
                           sort_keys=False)

        self.logger.start()

    @property
    def created(self) -> str:
        return self._created

    @property
    def experiments(self) -> tuple[str, ...]:
        return tuple(self._experiments.keys())

    @property
    def file(self) -> Path:
        return self.directory.joinpath("organization.exporgo")

    @property
    def last_modified(self) -> str:
        return self.modifications[0][1]

    @property
    def modifications(self) -> tuple:
        return tuple(self._modifications)

    @classmethod
    def load(cls, file: Optional[str | Path] = None) -> "Subject":
        file = file if file else select_file(title="Select organization file")
        if not file.is_file():
            file = file.joinpath("organization.exporgo")
        with open(file, "r") as file:
            _dict = yaml.safe_load(file)
        return cls.__from_dict__(_dict)

    @classmethod
    def __from_dict__(cls, _dict: dict) -> "Subject":
        subject = cls(
            name=_dict.get("name"),
            directory=_dict.get("directory"),
            species=_dict.get("species"),
            study=_dict.get("study"),
            condition=_dict.get("condition"),
            meta=_dict.get("meta"),
            start_log=False
        )

        for experiment_name, experiment_dict in _dict.get("experiments").items():
            subject.create_experiment(experiment_name, experiment_dict.pop("mix_ins"), index=False)
            experiment = subject.get(experiment_name)
            experiment.file_tree = FileTree.__from_dict__(experiment_dict.pop("file_tree"))
            experiment.__dict__.update(experiment_dict)

        subject._created = _dict.get("created")
        subject._modifications = ModificationLogger(_dict.get("modifications"))
        subject.logger.start()

        return subject

    def create_experiment(self, name: str, mix_ins: str | Experiment | Iterable[str | Experiment], **kwargs) -> None:
        factory = ExperimentFactory(name=name, base_directory=self.directory)
        factory.add_mix_ins(mix_ins)

        if name in self.experiments:
            raise DuplicateExperimentError(name)

        self._experiments[name] = factory.instance_constructor(**kwargs)
        self.record(name)

    def record(self, info: str = None) -> None:
        self._modifications.appendleft(info)

    def index(self) -> None:
        for experiment_name in self.experiments:
            experiment = getattr(self, experiment_name)
            experiment.index()

    def validate(self) -> None:
        missing = {}
        for experiment in self._experiments.values():
            try:
                experiment.validate()
            except MissingFilesError as exc:
                missing.update(exc.missing_files)

        if missing:
            raise MissingFilesError(missing)

    def get(self, key: str) -> Any:
        return getattr(self, key)

    def __to_dict__(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "created": self.created,
            "last_modified": self.last_modified,
            "directory": str(self.directory),
            "file": str(self.file),
            "species": self.species,
            "study": self.study,
            "condition": self.condition,
            "meta": self.meta,
            "experiments": {name: experiment.__to_dict__() for name, experiment in self._experiments.items()},
            "modifications": self.modifications,
        }

    def __repr__(self) -> str:
        return "".join([
            f"{self.__class__.__name__}"
            f"({self.name=}, "
            f"{self.directory=}, "
            f"{self.species=}, "
            f"{self.study=}, "
            f"{self.condition=}, "
            f"{self.meta=}): "
            f"{self.experiments=}, ",
            f"{self.exporgo_file=}, "
            f"{self.modifications=}, "
            f"{self._created=}"
        ])

    def __getattr__(self, item: str) -> Any:
        if item in self.experiments:
            return self._experiments.get(item)
        else:
            return super().__getattribute__(item)

    def __setattr__(self, key: Any, value: Any) -> None:
        """
        Override magic to auto-record modifications
        """
        super().__setattr__(key, value)
        self.record(key)

    def __del__(self):
        if "logger" in vars(self):
            self.logger.end()
            self.logger._IP = None
