# noinspection PyProtectedMember
from exporgo._color import TERMINAL_FORMATTER


def test_terminal_scheme():
    # check properties
    for attr in ["emphasis", "header", "announcement"]:
        getattr(TERMINAL_FORMATTER, attr)

    # check all styles unique
    keys = [key for key in dir(TERMINAL_FORMATTER) if key.isupper()]
    assert len(keys) == len({getattr(TERMINAL_FORMATTER, key) for key in keys})

    # check wrapping messages actually resets
    new_msg = TERMINAL_FORMATTER("42!", "emphasis")
    msg_parts = new_msg.split("!")
    assert msg_parts[-1] == "\x1b[0m"

    # check msg still delivered if failed style request
    new_msg = TERMINAL_FORMATTER("42!", "Adams")
    assert "42!" in new_msg
