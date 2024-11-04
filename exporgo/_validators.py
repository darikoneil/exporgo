import string
import warnings
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Tuple

from pydantic import ConfigDict

from . import __current_version__
from .exceptions import (InvalidExtensionWarning, InvalidFilenameError,
                         NotPermittedTypeError, UpdateVersionWarning,
                         VersionBackwardCompatibilityError,
                         VersionBackwardCompatibilityWarning,
                         VersionForwardCompatibilityWarning)

"""
Some functions useful for validation. Most of these functions are parameterized decorators that can be used to
validate function arguments or perform runtime conversion between types that are commensurable but can't be directly
duck-typed.
"""


__all__ = [
    "convert_permitted_types_to_required",
    "validate_extension",
    "validate_filename",
    "validate_version",
]


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Internal Functions
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


def _amend_args(arguments: tuple, amendment: Any, pos: int = 0) -> tuple:
    """
    Function amends arguments tuple (~scary tuple mutation~)

    :param arguments: arguments to be amended

    :param amendment: new value of argument

    :param pos: index of argument to be converted

    :returns: amended arguments tuple
    """
    arguments = list(arguments)
    arguments[pos] = amendment
    return tuple(arguments)


def _collector(pos: int, key: str, *args, **kwargs) -> Tuple[bool, Any, bool]:
    """
    Function collects the argument to be validated

    :param pos: position of argument to be collected

    :param key: key of argument to be collected

    :param args: arguments for positional collection

    :param kwargs: keyword arguments for keyword collection

    :returns: A tuple containing an argument, target, and a boolean indicating whether to use positional arguments
    """
    # noinspection PyBroadException
    try:
        if key in kwargs:
            collected = True
            use_args = False
            target = kwargs.get(key)
        elif pos is not None and args[pos] is not None:
            collected = True
            use_args = True
            target = args[pos]
        else:
            raise Exception

    except Exception:  # if any exception, just report a failure to collect
        collected = False
        use_args = None
        target = None

    # noinspection PyUnboundLocalVariable
    return collected, target, use_args


def _parameterize(decorator: Callable) -> Callable:
    """
    Function for parameterizing decorators

    :param decorator: A decorator to parameterize

    :returns: A decorator that can be parameterized
    """

    def outer(*args, **kwargs) -> Callable:
        """
        Outer function that takes arguments and keyword arguments for the decorator

        :param args: Positional arguments for the decorator

        :param kwargs: Keyword arguments for the decorator

        :returns: A function that applies the decorator to the target function
        """

        def inner(func: Callable) -> Callable:
            """
            Inner function that applies the decorator to the target function

            :param func: The target function to be decorated

            :returns: The decorated function
            """
            # noinspection PyArgumentList
            return decorator(func, *args, **kwargs)

        return inner

    return outer


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Validation Decorators
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


@_parameterize
def convert_permitted_types_to_required(function: Callable,
                                        permitted: tuple,
                                        required: Any,
                                        pos: int = 0,
                                        key: str = None,
                                        ) -> Callable:
    """
    Decorator that converts an argument from any of the permitted types to the expected/required type.

    :param function: function to be decorated

    :param permitted: the types permitted by code

    :param required: the type required by code

    :param pos: index of argument to be converted

    :param key: keyword of argument to be converted

    :returns: decorated function

    :raises: :class:`NotPermittedTypeError <exceptions.NotPermittedTypeError>`

    .. warning::  The required type must be capable of converting the permitted types using the __call__ magic method.
    """
    @wraps(function)
    def decorator(*args, **kwargs) -> Callable:

        collected, allowed_input, use_args = _collector(pos, key, *args, **kwargs)

        if collected:
            if isinstance(allowed_input, permitted):
                allowed_input = required(allowed_input)

            if not isinstance(allowed_input, required):
                raise NotPermittedTypeError(key, pos, permitted, allowed_input)

            if use_args:
                args = _amend_args(args, allowed_input, pos)
            else:
                kwargs[key] = allowed_input

        return function(*args, **kwargs)

    return decorator


@_parameterize
def validate_extension(function: Callable, required_extension: str, pos: int = 0, key: str = None) -> Callable:
    """
    Decorator for validating a required extension on a file path

    :param function: function to be decorated

    :param required_extension: required extension

    :param pos: index of the argument to be validated

    :param key: keyword of the argument to be validated

    :returns: decorated function

    raises:: :class:`InvalidExtensionWarning <exceptions.InvalidExtensionWarning>`

    .. note:: This decorator will convert the extension of the file to the required extension if it is not already,
        rather than raising a fatal error.
    """
    @wraps(function)
    def decorator(*args, **kwargs) -> Callable:
        _original_type = type(args[pos])
        if not Path(args[pos]).suffix:
            args = _amend_args(args, _original_type("".join([str(args[pos]), required_extension])), pos)
        if Path(args[pos]).suffix != required_extension:
            warnings.warn(InvalidExtensionWarning(key, pos, Path(args[pos]).suffix, required_extension),
                          stacklevel=4)
            args = _amend_args(args, _original_type(Path(args[pos]).with_suffix(required_extension)), pos)
        # noinspection PyArgumentList
        return function(*args, **kwargs)
    return decorator


@_parameterize
def validate_filename(function: Callable, pos: int = 0, key: str = None) -> Callable:
    """
    Decorator for validating filenames adhere to best practices for naming files. Specifically, filenames should only
    contain ascii letters, digits, periods, and underscores. The decorator will validate the entire path, not just
    the filename.

    :param function: function to be decorated

    :param pos: index of the argument to be validated

    :param key: keyword of the argument to be validated

    :returns: decorated function

    raises:: :class:`InvalidFilenameError <exceptions.InvalidFilenameError>`

    .. note:: See `here <https://docs.microsoft.com/en-us/windows/win32/fileio/naming-a-file>1_ for more information
        on file naming best practices for naming files.
    """
    @wraps(function)
    def decorator(*args, **kwargs) -> Callable:

        collected, allowed_input, use_args = _collector(pos, key, *args, **kwargs)

        if collected:
            if use_args:
                string_input = str(args[pos])
            else:
                string_input = str(kwargs.get(key))
            string_input = string_input.split("\\")[-1]
            if not set(string_input) <= set(string.ascii_letters + string.digits + "." + "_"):
                raise InvalidFilenameError(key, pos, string_input)

        # noinspection PyArgumentList
        return function(*args, **kwargs)
    return decorator


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Validation Functions
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


def validate_version(version: str) -> None:
    """
    Validate the compatibility of the organization's exporgo version with currently installed version of the package

    :param version: detected version

    :raises VersionForwardCompatibilityWarning: Raised if the detected major version is ahead of the installed
        major version

    :raises VersionBackwardCompatibilityError: Raised if the detected major version is behind the installed
        major version

    :raises VersionBackwardCompatibilityWarning: Raised if the detected patch version is behind the installed
        patch version

    :raises UpdateVersionWarning: Raised if the detected patch version is ahead of the installed patch version
    """
    config_major, config_minor, config_patch = version.split(".")
    package_major, package_minor, package_patch = __current_version__.split(".")
    if int(config_major) < int(package_major):
        warnings.warn(VersionForwardCompatibilityWarning(version), stacklevel=2)
    elif int(config_major) > int(package_major):
        raise VersionBackwardCompatibilityError(version)
    elif int(config_minor) > int(package_minor):
        warnings.warn(VersionBackwardCompatibilityWarning(version), stacklevel=2)
    elif int(config_patch) > int(package_patch):
        warnings.warn(UpdateVersionWarning(version), stacklevel=2)


MODEL_CONFIG = ConfigDict(extra="forbid",
                          revalidate_instances="always",
                          validate_assignment=True,
                          validate_default=False
                          )
