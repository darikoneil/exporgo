from pathlib import Path

import pytest

# noinspection PyProtectedMember
from exporgo._version import __current_version__
from exporgo.exceptions import (InvalidExtensionWarning, InvalidFilenameError,
                                UpdateVersionWarning,
                                VersionBackwardCompatibilityError,
                                VersionBackwardCompatibilityWarning,
                                VersionForwardCompatibilityWarning)
# noinspection PyProtectedMember
from exporgo.validators import (validate_extension, validate_filename,
                                validate_version)


def test_validate_extension():
    # generate_decorated function
    # noinspection PyUnusedLocal
    @validate_extension(parameter="a", required_extension=".marvin")
    def valid_handle(a, b):
        return 0

    # test valid
    valid_handle("C:\\the_paranoid_android.marvin", None)
    valid_handle(Path("C:\\the_paranoid_android.marvin"), None)
    # test invalid
    with pytest.warns(InvalidExtensionWarning):
        valid_handle(Path("C:\\the_paranoid_android.arthur"), None)


def test_validate_filename():
    # noinspection PyUnusedLocal
    @validate_filename(parameter="a")
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

