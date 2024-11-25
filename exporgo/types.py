from enum import Enum, IntEnum, auto
from os import PathLike
from pathlib import Path
from types import GeneratorType
from typing import Callable

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
    def __str__(self) -> str:
        return self.value

    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str:  # noqa: U100
        return name

class _ExporgoIntEnum(IntEnum):
    """
    IntEnum that can be serialized (and todo: validated)
    """

    def __serialize__(self) -> str:
        return f"({self.name}, {self.value})"


class Category(_ExporgoIntEnum):
    PREPARE = 0
    ANALYZE = 1
    SUMMARIZE = 2


class FileFormats(_AutoStrEnum):
    JSON = auto()
    YAML = auto()
    TOML = auto()


class Priority(_ExporgoIntEnum):
    IDLE = 0
    LOW = 1
    BELOW_NORMAL = 2
    NORMAL = 3
    ABOVE_NORMAL = 4
    HIGH = 5
    CRITICAL = 6


class Status(_ExporgoIntEnum):
    ERROR = -2
    EMPTY = -1
    SOURCE = 0
    COLLECT = 1
    ANALYZE = 2
    SUCCESS = 3


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Custom Types Aliases
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


Analysis = str | Path | Callable
# TODO: I'm not sure if this is the best way to do this or necessary (Analysis)

File = str | Path | PathLike

Folder = str | Path | PathLike

CollectionType = list | tuple | set | GeneratorType
# TODO: I'm not sure if this is the best way to do this or necessary (CollectionType)

Modification = tuple[str, str]
# TODO: I'm not sure if this is the best way to do this or necessary (Modification)
