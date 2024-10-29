from pydantic import BaseModel, Field
from enum import Enum,auto


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// String-based enumerations for exporgo
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class _AutoStrEnum(str, Enum):
    """
    StrEnum where enum.auto() returns the field name.
    See https://docs.python.org/3.9/library/enum.html#using-automatic-values
    From https://stackoverflow.com/questions/58608361/string-based-enum-in-python
    """
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str:
        return name
        # Or if you prefer, return lower-case member (it's StrEnum default behavior since Python 3.11):
        # return name.lower()

    def __str__(self) -> str:
        return self.value  # type: ignore


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Setting enumerations for exporgo
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class Priority(Enum):
    CRITICAL = 0
    HIGH = 1
    ABOVE_NORMAL = 2
    NORMAL = 3
    BELOW_NORMAL = 4
    LOW = 5
    IDLE = 6


class FileFormats(_AutoStrEnum):
    JSON = auto()
    YAML = auto()
    TOML = auto()


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// General settings for exporgo
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class ExporgoSettings(BaseModel):
    file_format:  FileFormats = Field(FileFormats.JSON, title="File format for storing experiment configurations")
