import json
from contextlib import suppress
from functools import singledispatchmethod
from pathlib import Path
from textwrap import indent
from types import GeneratorType
from typing import TYPE_CHECKING, Any, Callable, Optional

from portalocker import Lock
from portalocker.constants import LOCK_EX
from portalocker.exceptions import BaseLockException
from pydantic import BaseModel, field_serializer, field_validator

from exporgo._color import TERMINAL_FORMATTER
from exporgo.exceptions import (AnalysisNotRegisteredError,
                                DuplicateRegistrationError)
# noinspection PyProtectedMember
from exporgo.tools import serialize_function
from exporgo.validators import (MODEL_CONFIG, validate_dumping_with_pydantic,
                                validate_method_with_pydantic)

if TYPE_CHECKING:
    from .subject import Subject

from ..io import import_function_from_file
from ..types import Action, Category, CollectionType, File, Status

"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Step Model for Serialization and Validation
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class ValidStep(BaseModel):
    key: str
    call: Action
    file_sets: Optional[str | list[str] | tuple[str, ...]] = None
    category: Category = Category.ANALYZE
    status: Status = Status.SOURCE
    model_config = MODEL_CONFIG

    @field_serializer("call", check_fields=True)
    @classmethod
    def serialize_call(cls, v: File | Callable) -> str | dict:
        if isinstance(v, Callable):
            return serialize_function(v)
        else:
            return str(v)

    @field_serializer("category", check_fields=True)
    @classmethod
    def serialize_category(cls, v: Category) -> str:
        return v.__serialize__()

    @field_serializer("status", check_fields=True)
    @classmethod
    def serialize_status(cls, v: Status) -> str:
        return v.__serialize__()

    @field_validator("call", mode="before", check_fields=True)
    @classmethod
    def validate_call(cls, v: Any) -> str | Path | Callable:
        if isinstance(v, dict):
            return import_function_from_file(v["name"], v["file"])
        else:
            return v  # pragma: no cover

    @field_validator("category", mode="before", check_fields=True)
    @classmethod
    def validate_category(cls, v: Any) -> Category:
        with suppress(ValueError):
            return Category(v)
        return Category.__deserialize__(v)

    @field_validator("status", mode="before", check_fields=True)
    @classmethod
    def validate_status(cls, v: Any) -> Status:
        with suppress(ValueError):
            return Status(v)
        return Status.__deserialize__(v)


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Step Class
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class Step:

    def __init__(self,
                 key: str,
                 call: Action,
                 file_sets: str | list[str] | tuple[str, ...],
                 category: Category,
                 status: Status = Status.SOURCE):
        self._key = key
        self._call = call
        self._file_sets = file_sets
        self._category = category
        self.status = status

    @property
    def call(self) -> str | Path | Callable:
        return self._call
    # TODO: Implement file-based (scripts, jupyter notebooks, etc.) calls, make this just descriptive?

    @property
    def category(self) -> Category:
        return self._category

    @property
    def file_sets(self) -> str | CollectionType:
        return self._file_sets

    @property
    def key(self) -> str:
        return self._key

    @property
    def status(self) -> Status:
        return self._status

    @classmethod
    @validate_method_with_pydantic(ValidStep)
    def __deserialize__(cls,
                        key: str,
                        call: str | Path | Callable,
                        file_sets: str | list[str] | tuple[str, ...],
                        category: Category,
                        status: Status
                        ) -> "Step":
        return Step(key, call, file_sets, category, status)

    @classmethod
    @validate_dumping_with_pydantic(ValidStep)
    def __serialize__(cls, self: "Step") -> dict:
        # noinspection PyTypeChecker
        return dict(self)

    @status.setter
    def status(self, value: Status) -> None:
        self._status = Status(value)

    def __call__(self, subject: File or "Subject"):
        if isinstance(self._call, Callable):
            self._call(subject)
        elif isinstance(self._call, File):
            raise NotImplementedError("File-based calls are not yet supported")
        else:
            raise TypeError("Invalid call type")

    def __eq__(self, other: Any) -> bool:  # pragma: no cover
        try:
            return self.key == other.key
        except AttributeError:
            return False

    def __ne__(self, other: Any) -> bool:  # pragma: no cover
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.__repr__())    # pragma: no cover  # noqa: ANN201


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Step Registry
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class RegisteredStep(BaseModel, extra="ignore"):
    key: str
    call: Action
    file_sets: str | list[str] | tuple[str, ...]
    category: Category = Category.ANALYZE
    model_config = MODEL_CONFIG

    @field_serializer("call", check_fields=True)
    @classmethod
    def serialize_call(cls, v: str | Path | Callable) -> str | dict:
        if isinstance(v, Callable):
            return serialize_function(v)
        else:
            return str(v)

    @field_serializer("category", check_fields=True)
    @classmethod
    def serialize_category(cls, v: Category) -> str:
        return f"({v.name}, {v.value})"

    @field_validator("call", mode="before", check_fields=True)
    @classmethod
    def validate_call(cls, v: Any) -> str | Path | Callable:
        if isinstance(v, dict):
            return import_function_from_file(v["name"], v["file"])
        else:
            return v  # pragma: no cover

    @field_validator("category", mode="before", check_fields=True)
    @classmethod
    def validate_category(cls, v: Any) -> Category:
        with suppress(ValueError):
            return Category(v)
        return Category.__deserialize__(v)

    def __serialize__(self) -> dict:
        return dict(self)

    def __eq__(self, other: Any) -> bool:  # pragma: no cover
        try:
            return self.key == other.key
        except AttributeError:
            return False

    def __ne__(self, other: Any) -> bool:  # pragma: no cover
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.__repr__())  # pragma: no cover  # noqa: ANN201


class StepRegistry:
    """
    Registry for storing analysis configurations
    """
    __registry = {}
    __path = Path(__file__).parent.joinpath("registry").joinpath("registered_steps.json")
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
                for idx, key_step in enumerate(cls.__registry.items()):
                    key, step = key_step
                    str_step = indent(json.dumps(key)
                                      + f": {step.model_dump_json(exclude_defaults=True, indent=4)}",
                                      " " * 4)
                    str_step = f"{str_step},\n" if idx != len(cls.__registry) - 1 else f"{str_step}\n"
                    file.write(str_step)
                file.write("}\n")
        except FileNotFoundError:
            cls.__path.touch(exist_ok=False)
            cls._save_registry()
        except (IOError, BaseLockException) as exc:
            print(TERMINAL_FORMATTER(f"\nError saving registry: {exc}\n\n", "announcement"))

    @classmethod
    def has(cls, key: str) -> bool:
        """
        Check if an analysis configuration is registered
        """
        return key in cls.__registry

    @classmethod
    def get(cls, key: str) -> "RegisteredStep":
        """
        Get an analysis configuration
        """
        if not cls.has(key):
            raise AnalysisNotRegisteredError(key)
        return cls.__registry[key]

    @classmethod
    def pop(cls, key: str) -> "RegisteredStep":
        """
        Remove an experiment configuration
        """
        if not cls.has(key):
            raise AnalysisNotRegisteredError(key)
        config = cls.__registry.pop(key)
        cls._save_registry()
        return config

    # noinspection PyNestedDecorators
    @singledispatchmethod
    @classmethod
    def register(cls, step: "RegisteredStep") -> None:
        """
        Register an experiment configuration
        """
        if step.key in cls.__registry:
            raise DuplicateRegistrationError(step.key)
        cls.__registry[step.key] = step
        cls.__new_registration = True

    # noinspection PyNestedDecorators
    @register.register
    @classmethod
    def _(cls, step: dict) -> None:
        cls.register(RegisteredStep(**step))

    # noinspection PyNestedDecorators
    @register.register(list)
    @register.register(tuple)
    @register.register(set)
    @register.register(GeneratorType)
    @classmethod
    def _(cls, step: CollectionType) -> None:
        for config in step:
            cls.register(config)

    # noinspection PyNestedDecorators
    @register.register
    @classmethod
    def _(cls, step: str, **kwargs) -> None:
        cls.register(Step(key=step, **kwargs))

    @register.register
    @classmethod
    def _(cls, step: Step) -> None:
        cls.register(RegisteredStep(**{
            "key": step.key,
            "call": step.call,
            "file_sets": step.file_sets,
            "category": step.category,
        }))

    # noinspection DuplicatedCode
    @classmethod
    def _load_registry(cls) -> None:
        # noinspection DuplicatedCode
        """
                Load the registry from a JSON file
                """
        try:
            with Lock(cls.__path, "r", timeout=10) as file:
                cls.__registry = {key: RegisteredStep.model_validate(config) for key, config in json.load(file).items()}
        except FileNotFoundError:
            cls.__path.touch(exist_ok=False)
            cls._save_registry()
        except (IOError, json.JSONDecodeError) as exc:
            print(TERMINAL_FORMATTER(f"\nError loading registry: {exc}\n\n", "announcement"))

    @classmethod
    def __enter__(cls) -> "StepRegistry":
        cls._load_registry()
        return StepRegistry()

    @classmethod
    def __exit__(cls, exc_type, exc_val, exc_tb):  # noqa: ANN206, ANN201, ANN001
        if cls.__new_registration:
            cls._save_registry()
