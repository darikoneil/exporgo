from pathlib import Path
from os import PathLike
from typing import Callable
from types import GeneratorType
from enum import Enum, auto


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Enumerations
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class _AutoStrEnum(str, Enum):
    """
    StrEnum where enum.auto() returns the field name.
    See https://docs.python.org/3.9/library/enum.html#using-automatic-values
    From https://stackoverflow.com/questions/58608361/string-based-enum-in-python
    """
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str:  # noqa: U100
        return name
        # Or if you prefer, return lower-case member (it's StrEnum default behavior since Python 3.11):
        # return name.lower()

    def __str__(self) -> str:
        return self.value  # type: ignore


class FileFormats(_AutoStrEnum):
    JSON = auto()
    YAML = auto()
    TOML = auto()


class Priority(Enum):
    CRITICAL = 0
    HIGH = 1
    ABOVE_NORMAL = 2
    NORMAL = 3
    BELOW_NORMAL = 4
    LOW = 5
    IDLE = 6


class Status(Enum):
    ERROR = 0
    SOURCE = 1
    COLLECT = 2
    ANALYZE = 3
    SUCCESS = 4


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Custom Types Aliases
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


Analysis = str| Path | Callable

File = str | Path | PathLike

Folder = str | Path | PathLike

CollectionType = list | tuple | set | GeneratorType

Modification = tuple[str, str]
