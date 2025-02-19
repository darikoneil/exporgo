from enum import IntEnum
from os import PathLike
from pathlib import Path
from types import GeneratorType
from typing import Callable

from .exceptions import EnumNameValueMismatchError

"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Enumerations
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class _ExporgoIntEnum(IntEnum):
    """
    :class:`IntEnum <enum.IntEnum>` that can be serialized and deserialized.
    """

    @classmethod
    def __deserialize__(cls, value: str) -> "_ExporgoIntEnum":
        if isinstance(value, str):
            name, value = value[1:-1].split(", ")
            value = int(value)
        elif isinstance(value, tuple):
            name, value = value
        else:
            raise TypeError(f"Cannot deserialize {value} into {cls.__name__}")
        enum_ = cls(value)

        try:
            assert enum_.name == name
        except AssertionError as exc:
            raise EnumNameValueMismatchError(cls, name, value) from exc
        return enum_

    def __serialize__(self) -> str:
        return f"({self.name}, {self.value})"


class Category(_ExporgoIntEnum):
    """
    Category enumeration declaring when a step is to be executed within a pipeline.
    """

    #: Prepares data for subsequent analysis.
    PREPARE = 0

    #: Performs analysis of data (default).
    ANALYZE = 1

    #: Summarizes or compiles analyzed data.
    SUMMARIZE = 2


class FileFormat(_ExporgoIntEnum):
    """
    File formats enumeration for setting the file format of the exporgo organization file.
    """

    #: YAML file format (default)
    YAML = 0

    #: JSON file format
    JSON = 1

    #: TOML file format
    TOML = 2


class Priority(_ExporgoIntEnum):
    """
    Priority enumeration for setting the priority of a step within a pipeline.
    """

    #: Analysis suggested by reviewer #2... The absolute lowest priority. Only executed when there literally is nothing
    #: else to do and even then, it's utterly pointless...
    IDLE = 0

    #: Low priority analysis to be executed when there is nothing better to do...
    LOW = 1

    #: Data that is not critical but should be analyzed...
    BELOW_NORMAL = 2

    #: Normal priority (default)
    NORMAL = 3

    #: This data is critical for interpreting the results!
    ABOVE_NORMAL = 4

    #: This needs to be analyzed before my lab meeting tomorrow!
    HIGH = 5

    #: I will fail my thesis defense if this is not executed immediately!
    CRITICAL = 6


class Status(_ExporgoIntEnum):
    """
    Status enumeration for setting the status of a step within a pipeline.
    """

    #: Error encountered during execution
    ERROR = -2

    #: There is nothing to do
    EMPTY = -1

    #: Data needs to be located
    SOURCE = 0

    #: Data needs to be collected and organized
    COLLECT = 1

    #: Data needs to be analyzed
    ANALYZE = 2

    #: Data analysis is complete
    SUCCESS = 3


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Custom Types Aliases
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""

#: Alias for step calls, which may be either a callable, or a string, Path, or or any PathLike object pointing to a
#: python script or parameterized jupyter notebook.
Action = str | Path | PathLike | Callable

#: Alias for a variable that can be a string, Path, or any PathLike object AND contains a file extension.
File = str | Path | PathLike

#: Alias for a variable that can be a string, Path, or any PathLike object AND does not contain a file extension.
Folder = str | Path | PathLike

#: Alias for a variable containing a collection of items (list, tuple, set, or generator).
CollectionType = list | tuple | set | GeneratorType

#: Alias for a modification, consisting of a tuple of two strings (description, timestamp)
Modification = tuple[str, str]
