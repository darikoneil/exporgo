from pathlib import Path
from typing import Any, Optional
from . import __current_version__, __package_name__


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// IO Errors and Warnings
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class InvalidFilenameError(ValueError):
    """
    Raised when an invalid filename is used

    :param key: key of the argument

    :param pos: position of the argument

    :param filename: filename that is invalid
    :type filename: :class:`str` or :class:`Path <pathlib.Path>`
    """
    def __init__(self, key: str, pos: int, filename: str | Path):
        self.key = key
        self.filename = filename
        self.pos = pos
        super().__init__(f"Argument {self.key} at position {self.pos} has invalid filename {self.filename}."
                         f"Please use only alphanumeric characters and underscores.")


class InvalidExtensionWarning(UserWarning):
    """
    Raised when an invalid file extension is used

    :param key: key of the argument

    :param pos: position of the argument

    :param extension: extension that is invalid

    :param permitted: permitted extension/s
    :type permitted: :class:`str` or :class:`tuple`\[:class:`str`\]

    :param coerced: coerced extension
    :type coerced: :class:`Optional <typing.Optional>`\[:class:`str`\], default: ```None```
    """
    def __init__(self,
                 key: str,
                 pos: int,
                 extension: str,
                 permitted: str | tuple[str, ...],
                 coerced: Optional[str] = None):
        self.key = key
        self.pos = pos
        self.extension = extension
        self.permitted = permitted
        self.coerced = coerced if coerced else permitted
        super().__init__(f"Argument {self.key} at position {self.pos} has invalid file extension {self.extension}. "
                         f"Expected extension {self.permitted} and coerced to {self.permitted}.")


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Validation (General) Errors and Warnings
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class NotPermittedTypeError(TypeError):
    """
    Raised when a type is not permitted

    :param key: key of the argument

    :param pos: position of the argument

    :param permitted: permitted type/s
    :type permitted: :class:`Any` or :class:`tuple`\[:class:`Any`\]
    """
    def __init__(self, key: str, pos: int, permitted: Any | tuple[Any, ...]):
        self.key = key
        self.pos = pos
        self.permitted = permitted
        super().__init__(f"Argument {self.key} at position {self.pos} must be of type {self.permitted}")


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Version Errors and Warnings
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


def _config_mismatch_message(version: str) -> str:
    """
    Message for version mismatch

    :param version: Detected version that mismatches the current version

    :return: Config mismatch introduction message
    """
    return (f"Imported organization was not saved with the current version of "
            f"{__package_name__} ({__current_version__}); detected version: {version}.")


class UpdateVersionWarning(UserWarning):
    """
    Raised when the organization's version is not the current version of the package. Use only when the mismatch is
    minimal

    :param version: detected version
    """
    def __init__(self, version: str):
        super().__init__(_config_mismatch_message(version))


class VersionForwardCompatibilityWarning(UserWarning):
    """
    Raised when the configuration version does not match the expected version (forward compatibility of major versions)

    :param version: detected version
    """
    def __init__(self, version: str):
        message = _config_mismatch_message(version)
        message += "Forward compatibility of major versions is not guaranteed!"
        super().__init__(message)


class VersionBackwardCompatibilityWarning(UserWarning):
    """
    Raised when the configuration version does not match the expected version (backward compatibility of minor versions)

    :param version: detected version
    """

    def __init__(self, version: str):
        super().__init__(f"{_config_mismatch_message(version)} "
                         f"Backward compatibility of minor versions is not guaranteed!")


class VersionBackwardCompatibilityError(ValueError):
    """
    Raised when the configuration version does not match the expected version

    :param version: detected version
    """
    def __init__(self, version: str):
        message = _config_mismatch_message(version)
        message += "Neurobeam does not support backwards compatibility of major versions!"
        super().__init__(message)


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Access Errors and Warnings
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""

class SingletonError(RuntimeError):
    """
    Raised when attempting to create a second instance of a singleton
    """

    def __init__(self, singleton: object):
        self.singleton = singleton
        name = self.singleton.__name__ if hasattr(self.singleton, "__name__") \
            else type(self.singleton).__name__
        super().__init__(f"{name} is a singleton and cannot be instantiated more than once")


class ImmutableInstanceWarning(RuntimeWarning):
    """
    Raised when attempting to set an attribute on an immutable instance
    """
    def __init__(self, instance: object):
        self.instance = instance
        super().__init__(f"{self.instance.__class__.__name__} is immutable and cannot be modified")
