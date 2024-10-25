from pathlib import Path
from typing import Any, Iterable, Optional

from ._color import TERMINAL_FORMATTER
from ._io import select_directory
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
        self._instance_date = get_timestamp()

        #: dict: experiments
        self._experiments = {}

        #: IPython_logger: logging object
        self._logger = IPythonLogger(self.directory)

        # call this only after all attrs successfully initialized
        self._modifications.append("Instantiated")

    def __str__(self) -> str:
        string_to_print = ""

        string_to_print += TERMINAL_FORMATTER(f"{self.name}\n", "header")
        string_to_print += TERMINAL_FORMATTER("Created: ", "emphasis")
        string_to_print += f"{self._instance_date}\n"
        string_to_print += TERMINAL_FORMATTER("Last Modified: ", "emphasis")
        string_to_print += f"{self.modifications[0]}\n"
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
            string_to_print += "\tNo meta data defined\n"
        else:
            for key, value in self.meta.items():
                string_to_print += TERMINAL_FORMATTER(f"\t{key}: ", "BLUE")
                string_to_print += f"{value}\n"
        string_to_print += TERMINAL_FORMATTER("Experiments:\n", "emphasis")

        if len(self.experiments) == 0:
            string_to_print += "\tNo experiments defined\n"
        for experiment in self.experiments:
            string_to_print += TERMINAL_FORMATTER(f"\t{experiment}\n", "experiment")

        string_to_print += TERMINAL_FORMATTER("Recent Modifications:\n", "modifications")
        for modification in self.modifications[-5:]:
            string_to_print += TERMINAL_FORMATTER(f"\t{modification[0]}: ", "BLUE")
            string_to_print += f"{modification[1]}\n"

        return string_to_print

    @property
    def modifications(self) -> tuple:
        return tuple(self._modifications)

    @property
    def experiments(self) -> tuple[str, ...]:
        return tuple(self._experiments.keys())

    @property
    def file(self) -> Path:
        return self.directory.joinpath("organization.exporgo")

    def create_experiment(self, name: str, mix_ins: str | Experiment | Iterable[str | Experiment]) -> None:
        factory = ExperimentFactory(name=name, base_directory=self.directory)
        factory.add_mix_ins(mix_ins)

        if name in self.experiments:
            raise DuplicateExperimentError(name)

        self._experiments[name] = factory.instance_constructor()
        self.record(name)

    def record(self, info: str = None) -> None:
        self._modifications.appendleft(info)

    def index(self) -> None:
        for experiment_name in self.experiments:
            experiment = getattr(self, experiment_name)
            experiment.index()

    def validate(self) -> None:
        missing = {}
        for experiment_name in self.experiments:
            experiment = getattr(self, experiment_name)
            try:
                experiment.validate()
            except MissingFilesError as exc:
                missing.update(exc.missing_files)

        if missing:
            raise MissingFilesError(missing)

    def log_status(self) -> None:
        return self._logger.check_log_status()

    def get(self, key: str) -> Any:
        return getattr(self, key)

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
            f"{self._instance_date=}"
        ])

    def __getattr__(self, item: str) -> Any:
        """
        Override magic to auto-record access
        """
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
        if "_logger" in vars(self):
            self._logger.end_log()
