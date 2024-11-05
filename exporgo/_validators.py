import string
import warnings
from functools import wraps
from pathlib import Path
from typing import Any, Callable
import inspect

from pydantic import ConfigDict

from . import __current_version__
from ._tools import amend_args, collector, parameterize
from .exceptions import (InvalidExtensionWarning, InvalidFilenameError,
                         NotPermittedTypeError, UpdateVersionWarning,
                         VersionBackwardCompatibilityError,
                         VersionBackwardCompatibilityWarning,
                         VersionForwardCompatibilityWarning)

"""
Some functions useful for validation & a conserved config for all Pydantic BaseModels. Most of these functions are 
parameterized decorators that can be used to validate function arguments or perform runtime conversion between types 
that are commensurable but can't be directly duck-typed.
"""


__all__ = [
    "convert_permitted_types_to_required",
    "validate_extension",
    "validate_filename",
    "validate_version",
    "MODEL_CONFIG",
]


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Validation Decorators
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


@parameterize
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

        collected, allowed_input, use_args = collector(pos, key, *args, **kwargs)

        if collected:
            if isinstance(allowed_input, permitted):
                allowed_input = required(allowed_input)

            if not isinstance(allowed_input, required):
                raise NotPermittedTypeError(key, pos, permitted, allowed_input)

            if use_args:
                args = amend_args(args, allowed_input, pos)
            else:
                kwargs[key] = allowed_input

        return function(*args, **kwargs)

    return decorator


@parameterize
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
            args = amend_args(args, _original_type("".join([str(args[pos]), required_extension])), pos)
        if Path(args[pos]).suffix != required_extension:
            warnings.warn(InvalidExtensionWarning(key, pos, Path(args[pos]).suffix, required_extension),
                          stacklevel=4)
            args = amend_args(args, _original_type(Path(args[pos]).with_suffix(required_extension)), pos)
        # noinspection PyArgumentList
        return function(*args, **kwargs)
    return decorator


@parameterize
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

        collected, allowed_input, use_args = collector(pos, key, *args, **kwargs)

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


@parameterize
def validate_dumping_with_pydantic(function: Callable, model: Any) -> Callable:
    # noinspection PyUnusedLocal
    @wraps(function)
    def decorator(class_, self_) -> Callable:
        # noinspection PyUnresolvedReferences,DuplicatedCode
        keys = model.model_fields.keys()
        params = {key: getattr(self_, key) for key in keys}
        valid_args = model(**params)
        return function(self_, valid_args.model_dump())

    return decorator



@parameterize
def validate_method_with_pydantic(function: Callable, model: Any) -> Callable:
    """
    Decorator for validating arguments with a Pydantic model

    :param function: function to be decorated

    :param model: Pydantic model to validate arguments

    :returns: decorated function

    :raises ValidationError: This decorator will raise a Pydantic ValidationError if the argument does not
        conform to the model
    """

    # noinspection PyUnusedLocal
    @wraps(function)
    def decorator(class_, *args, **kwargs) -> Callable:
        # noinspection PyUnresolvedReferences,DuplicatedCode
        sig = inspect.signature(function)
        bound_args = sig.bind_partial(*args, **kwargs)
        bound_args.apply_defaults()
        bound_args.arguments.pop("kwargs", None)
        keys = model.model_fields.keys()
        params = {key: bound_args.arguments.get("cls").get(key) for key in keys
                               if key in bound_args.arguments.get("cls")}
        valid_args = model(**params)
        return function(**{**bound_args.arguments, **vars(valid_args)})

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


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Pydantic Configuration
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""
MODEL_CONFIG = ConfigDict(extra="forbid",
                          revalidate_instances="always",
                          validate_assignment=True,
                          validate_default=False
                          )
