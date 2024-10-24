import pytest
# noinspection PyProtectedMember
from exporgo._validators import _collector, validate_extension
from exporgo.exceptions import InvalidExtensionWarning


def test_collector():
    # used kwargs
    args = None,
    kwargs = {"dummy": "dummy"}
    collected, target, use_args = _collector(0, "dummy", *args, **kwargs)
    assert collected
    assert not use_args
    assert (target == "dummy")

    # used args
    args = ("dummy", "variable")
    kwargs = {}
    collected, target, use_args = _collector(0, "dummy", *args, **kwargs)
    assert collected
    assert use_args
    assert (target == "dummy")

    # failure
    args = None,
    kwargs = {}
    collected, target, use_args = _collector(0, "dummy", *args, **kwargs)
    assert not collected
    assert not use_args
    assert not target


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
