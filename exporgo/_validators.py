import inspect
import string
import warnings
from contextlib import suppress
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from pydantic import ConfigDict

from . import __current_version__
from ._tools import amend_args, collector, parameterize
from .exceptions import (EnumNameValueMismatchError, InvalidExtensionWarning,
                         InvalidFilenameError, UpdateVersionWarning,
                         VersionBackwardCompatibilityError,
                         VersionBackwardCompatibilityWarning,
                         VersionForwardCompatibilityWarning)
from .types import Category, Priority, Status

"""
Some functions useful for validation & a conserved config for all Pydantic BaseModels. Most of these functions are
parameterized decorators that can be used to validate function arguments or perform runtime conversion between types
that are commensurable but can't be directly duck-typed.
"""


__all__ = [
    "validate_extension",
    "validate_filename",
    "validate_version",
    "validate_priority",
    "validate_status",
    "validate_dumping_with_pydantic",
    "validate_method_with_pydantic",
    "validate_category",
    "MODEL_CONFIG",
]


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Validation Decorators
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


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
    """
    Decorator for validating the dumping of class attributes with a Pydantic model.

    :param function: The class function to be decorated.

    :param model: The Pydantic model to validate the class attributes.

    :returns: The decorated function.

    .. warning :: This decorator is only intended for use with class methods that accept an instance of the class as
        the first argument.

    """

    # noinspection PyUnusedLocal
    @wraps(function)
    def decorator(class_, self_) -> Callable:  # noqa: ANN001, U100
        """
        Inner decorator function that performs the validation.

        :param class_: The class being decorated.

        :param self_: The instance of the class.

        :returns: The result of the decorated function.
        """
        params = {key: getattr(self_, key) for key in model.model_fields.keys()}
        valid_args = model(**params)
        return function(self_, valid_args.model_dump())

    return decorator


@parameterize
def validate_method_with_pydantic(function: Callable, model: Any) -> Callable:
    """
    Decorator for validating method arguments with a Pydantic model.

    :param function: The function to be decorated.

    :param model: The Pydantic model to validate the method arguments.

    :returns: The decorated function.

    .. warning :: This decorator is only intended for use with class methods
    """

    # noinspection PyUnusedLocal
    @wraps(function)
    def decorator(class_, *args, **kwargs) -> Callable:  # noqa: ANN001, U100
        """
        Inner decorator function that performs the validation.

        :param class_: The class being decorated.

        :param args: Positional arguments for the method.

        :param kwargs: Keyword arguments for the method.

        :returns: The result of the decorated function.
        """
        # Get the signature of the function
        sig = inspect.signature(function)
        # Bind the arguments to the function signature
        bound_args = sig.bind_partial(*args, **kwargs)
        bound_args.apply_defaults()
        bound_args.arguments.pop("kwargs", None)
        # I don't know why, but I gotta do this ->
        if "cls" in bound_args.arguments:
            func_get = lambda key: bound_args.arguments.get("cls").get(key)  # noqa: E731
            container = bound_args.arguments.get("cls")
            has_cls = True
        else:
            func_get = lambda key: bound_args.arguments.get(key)  # noqa: E731
            container = bound_args.arguments
            has_cls = False
        # TODO: Read up on this, I don't know why I have to do this
        # Collect the parameters from the bound arguments that are in the Pydantic model
        params = {key: func_get(key) for key in model.model_fields.keys()
                  if key in container}
        # Validate the parameters with the Pydantic model
        valid_args = model(**params)
        # Call the original function with the validated arguments (class and validated arguments)
        if has_cls:
            return function(**{**bound_args.arguments, **vars(valid_args)})
        else:
            return function(class_, **{**vars(valid_args)})

    return decorator


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Validation Functions
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


# noinspection PyUnboundLocalVariable
def validate_category(v: Any) -> Category:
    with suppress(ValueError):
        return Category(v)
    if isinstance(v, str):
        name, value = v[1:-1].split(", ")
        value = int(value)
    elif isinstance(v, tuple):
        name, value = v
    category = Category(value)
    try:
        assert category.name == name
    except AssertionError as exc:
        raise EnumNameValueMismatchError(Category, name, value) from exc
    return category


# noinspection PyUnboundLocalVariable
def validate_priority(v: Any) -> Priority:
    with suppress(ValueError):
        return Priority(v)
    if isinstance(v, str):
        name, value = v[1:-1].split(", ")
        value = int(value)
    elif isinstance(v, tuple):
        name, value = v
    priority = Priority(value)
    try:
        assert priority.name == name
    except AssertionError as exc:
        raise EnumNameValueMismatchError(Priority, name, value) from exc
    return priority


# noinspection PyUnboundLocalVariable
def validate_status(v: Any) -> Status:
    with suppress(ValueError):
        return Status(v)
    if isinstance(v, str):
        name, value = v[1:-1].split(", ")
        value = int(value)
    elif isinstance(v, tuple):
        name, value = v
    status = Status(value)
    try:
        assert status.name == name
    except AssertionError as exc:
        raise EnumNameValueMismatchError(Status, name, value) from exc
    return status


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
                          validate_default=False,
                          arbitrary_types_allowed=True,
                          )
