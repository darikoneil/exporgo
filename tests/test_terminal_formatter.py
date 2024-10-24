import pytest

# noinspection PyProtectedMember
from exporgo._color import TERMINAL_FORMATTER, _TerminalFormatter
from exporgo.exceptions import ImmutableInstanceWarning, SingletonError


def test_terminal_scheme():

    # check properties
    for attr in ["type", "emphasis", "header", "announcement"]:
        getattr(TERMINAL_FORMATTER, attr)

    # check all styles unique
    keys = [key for key in dir(TERMINAL_FORMATTER) if key.isupper()]
    assert (len(keys) == len({getattr(TERMINAL_FORMATTER, key) for key in keys}))

    # check wrapping messages actually resets
    new_msg = TERMINAL_FORMATTER("42!", "type")
    msg_parts = new_msg.split("!")
    assert(msg_parts[-1] == "\x1b[0m")

    # check msg still delivered if failed style request
    new_msg = TERMINAL_FORMATTER("42!", "Adams")
    assert("42!" in new_msg)

    # check immutable
    with pytest.warns(ImmutableInstanceWarning):
        TERMINAL_FORMATTER.BLUE = "new_type"

    # finally check singleton status
    with pytest.raises(SingletonError):
        _ = _TerminalFormatter()


