from pathlib import Path
from typing import Any, Iterable, Optional

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
        return "SUBJECT"
    # TODO: Implement

    @property
    def modifications(self) -> tuple:
        return tuple(self._modifications)

    @property
    def experiments(self) -> tuple[str, ...]:
        return tuple([name for name, experiment in vars(self).items() if isinstance(experiment, Experiment)])

    @property
    def exporgo_file(self) -> Path:
        return self.directory.joinpath("exporgo.json")

    def create_experiment(self, name: str, mix_ins: Iterable[str | Experiment]) -> None:
        factory = ExperimentFactory(name=name, base_directory=self.directory)
        factory.add_mix_ins(mix_ins=mix_ins)
        setattr(self, name, factory.instance_constructor())

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

    def __setattr__(self, key: Any, value: Any) -> None:
        """
        Override magic to auto-record modifications
        """
        super().__setattr__(key, value)
        self.record(key)

    def __del__(self):
        if "_logger" in vars(self):
            self._logger.end_log()
