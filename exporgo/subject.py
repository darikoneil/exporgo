from pathlib import Path
from typing import Any, Iterable, Optional
from json_tricks import dump, load

from ._color import TERMINAL_FORMATTER
from ._io import select_directory
from ._logging import IPythonLogger, ModificationLogger, get_timestamp
from .exceptions import MissingFilesError
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
        self.directory = Path(directory) if directory else select_directory(title="Select folder to contain "
                                                                            "subject's organized data")
        if name not in self.directory.name:
            self.directory = self.directory.joinpath(name)
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

        #: IPython_logger: logging object
        self._logger = IPythonLogger(self.directory)

        # call this only after all attrs successfully initialized
        self._modifications.append("Instantiated")

    def __str__(self) -> str:
        attr_to_print = [("Subject: ", self.name),
                         ("Instantiated: ", self._instance_date),
                         ("Study: ", self.study),
                         ("Condition: ", self.condition),
                         ("Experiments: ", self.experiments)
                         ]

        string_to_print = "\n"
        for attr in attr_to_print:
            key, value = attr
            if key == "Experiments: ":
                string_to_print += f"\n{TERMINAL_FORMATTER.BOLD}{TERMINAL_FORMATTER.YELLOW}{key}{TERMINAL_FORMATTER.RESET}\n"
                for experiment in value:
                    string_to_print += f"\t{experiment}\n"
            else:
                string_to_print += f"\n{TERMINAL_FORMATTER.BOLD}{TERMINAL_FORMATTER.YELLOW}{key}{TERMINAL_FORMATTER.RESET}{value}"

        string_to_print += f"\n\nLast modified: {TERMINAL_FORMATTER.GREEN}{self.modifications[0][0]}{TERMINAL_FORMATTER.RESET}" \
                           f", {TERMINAL_FORMATTER.GREEN}{self.modifications[0][1]}{TERMINAL_FORMATTER.RESET}"

        return string_to_print
    # TODO: add __repr__ method & refactor

    def save(self) -> None:
        """
        Saves the subject to the directory. The organization of the subject's data is saved in a json file,
        which can be loaded back in to reconstruct the subject. The log file is also saved in the form of a text file
        (.log) in the subject's directory.
        """
        # temporarily close logging
        self._logger.end_log()
        # dump is manipulative so:
        with open(self.organization_file, "w") as file:
            dump(self, file, indent=4)

        self._logger.start_log()
        # TODO: refactor

    @property
    def modifications(self) -> tuple:
        return tuple(self._modifications)

    @property
    def experiments(self) -> tuple[str, ...]:
        return tuple([name for name, experiment in vars(self).items() if isinstance(experiment, Experiment)])

    @property
    def organization_file(self) -> Path:
        return self.directory.joinpath("organization_file.json")

    @classmethod
    def load(cls, directory: Optional[str | Path] = None) -> "Subject":
        if not directory:
            directory = select_directory(title="Select folder containing previously saved subject", mustexist=True)

        organization_file = directory.joinpath("organization_file.json")

        with open(organization_file, "r") as file:
            mouse = load(file, preserve_order=False)

        # now we have to manually update our experiment mix-ins
        for key, value in vars(mouse).items():
            if isinstance(value, Experiment):
                experiment = getattr(mouse, key)
                setattr(mouse, key, experiment.__json_construct__(experiment))

        # update directory if we've moved our folder since then
        if mouse.directory != directory:
            mouse.directory = directory  # we don't need this check really,
            # but it's here atm to eventually add child updates

        return mouse
        # TODO: refactor

    def create_experiment(self, name: str, mix_ins: Iterable[Experiment]) -> None:
        factory = ExperimentFactory(name=name, base_directory=self.directory)
        factory.add_mix_ins(mix_ins=mix_ins)
        setattr(self, name, factory.instance_constructor())
        # TODO: refactor

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

    def __json_encode__(self):
        serialized_mouse = {key: value for key, value in vars(self).items()}  # noqa: C416
        # unnecessary dict comprehension but now I can have big line saying make sure I'm a copy not a view

        # noinspection PyProtectedMember
        serialized_mouse["_modifications"] = self._modifications
        for key, value in serialized_mouse.items():
            if isinstance(value, Experiment):
                serialized_mouse[key] = {
                    "__instance_type__": ["CalSciPy.organization.experiment", "Experiment"],
                    "attributes": serialized_mouse[key].__json_encode__()
                }
        return serialized_mouse
        # TODO: Review

    def __setattr__(self, key: Any, value: Any) -> None:
        """
        Override magic to auto-record modifications
        """
        super().__setattr__(key, value)
        self.record(key)

    def __del__(self):
        if "_logger" in vars(self):
            self._logger.end_log()
