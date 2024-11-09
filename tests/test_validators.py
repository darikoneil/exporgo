from pathlib import Path

import pytest

from exporgo import __current_version__
from exporgo._tools import collector, convert
# noinspection PyProtectedMember
from exporgo._validators import (validate_extension, validate_filename,
                                 validate_version)
from exporgo.exceptions import (InvalidExtensionWarning, InvalidFilenameError,
                                UpdateVersionWarning,
                                VersionBackwardCompatibilityError,
                                VersionBackwardCompatibilityWarning,
                                VersionForwardCompatibilityWarning)


def test_collector():
    # used kwargs
    args = None,
    kwargs = {"dummy": "dummy"}
    collected, target, use_args = collector(0, "dummy", *args, **kwargs)
    assert collected
    assert not use_args
    assert (target == "dummy")

    # used args
    args = ("dummy", "variable")
    kwargs = {}
    collected, target, use_args = collector(0, "dummy", *args, **kwargs)
    assert collected
    assert use_args
    assert (target == "dummy")

    # failure
    args = None,
    kwargs = {}
    collected, target, use_args = collector(0, "dummy", *args, **kwargs)
    assert not collected
    assert not use_args
    assert not target


def test_convert_permitted_types_to_required():
    # generate_decorated function
    # noinspection PyUnusedLocal
    @convert(parameter="a", permitted=(str, Path), required=Path)
    def valid_handle(a, b):
        return 0

    # test valid
    valid_handle("C:\\sqornshellous.zem", None)

    # test invalid
    with pytest.raises(TypeError):
        valid_handle(0, None)


def test_validate_extension():
    # generate_decorated function
    # noinspection PyUnusedLocal
    @validate_extension(required_extension=".marvin", pos=0, key="a")
    def valid_handle(a, b):
        return 0

    # test valid
    valid_handle("C:\\the_paranoid_android.marvin", None)
    # test invalid
    with pytest.warns(InvalidExtensionWarning):
        valid_handle("C:\\the_paranoid_android.arthur", None)


def test_validate_filename():
    @validate_filename(pos=0, key="a")
    def valid_handle(a, b):
        return 0

    valid_handle("C:\\the_infinitely_prolonged.wowbagger", None)
    with pytest.raises(InvalidFilenameError):
        valid_handle("C:\\the_infinitely_$$ prolonged.wowbagger", None)


def test_validate_version():

    validate_version(__current_version__)

    split_version = [int(version) for version in __current_version__.split(".")]

    with pytest.warns(VersionForwardCompatibilityWarning):
       validate_version(f"{split_version[0] - 1}.{split_version[1]}.{split_version[2]}")

    with pytest.raises(VersionBackwardCompatibilityError):
        validate_version(f"{split_version[0] + 1}.{split_version[1]}.{split_version[2]}")

    with pytest.warns(VersionBackwardCompatibilityWarning):
        validate_version(f"{split_version[0]}.{split_version[1] + 1}.{split_version[2]}")

    with pytest.warns(UpdateVersionWarning):
        validate_version(f"{split_version[0]}.{split_version[1]}.{split_version[2] + 1}")

