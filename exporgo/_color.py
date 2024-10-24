from operator import eq
from typing import Any
from warnings import warn

from sqlalchemy.testing.plugin.plugin_base import warnings

from .exceptions import ImmutableInstanceWarning, SingletonError

"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Terminal Formatter
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class _TerminalFormatter:
    """
    A container class for exporgo's terminal printing color/font scheme

    :raise :class:`SingletonError` if instance already exists

    :raise :class:`ImmutableInstanceWarning` if attribute setting is attempted
    """
    YELLOW: str = "\u001b[38;5;11m"
    GREEN: str = "\033[38;2;64;204;139m"
    ORANGE: str = "\033[38;2;253;174;97m"
    RED: str = "\033[38;2;255;78;75m"
    BLUE: str = "\033[38;2;15;159;255m"
    BOLD: str = "\u001b[1m"
    UNDERLINE: str = "\u001b[7m"
    RESET: str = "\033[0m"

    def __new__(cls: "_TerminalFormatter") -> "_TerminalFormatter":
        """
        Force color scheme to exist as singleton
        """
        if not hasattr(cls, "instance"):
            # noinspection PyTypeChecker
            cls.instance = super(_TerminalFormatter, cls).__new__(cls)
        else:
            raise SingletonError(cls)
        return cls.instance

    def __str__(self):
        return "Terminal Formatter"

    @property
    def type(self) -> str:
        """
        :Getter: Blue font style for type hinting
        :Getter Type: :class:`str`
        """
        return self.BLUE

    @property
    def emphasis(self) -> str:
        """
        :Getter: Yellow font style for emphasis
        :Getter Type: :class:`str`
        """
        return self.YELLOW

    @property
    def header(self) -> str:
        """
        :Getter: Style for headers, titles and other things of utmost importance consisting of
            bold yellow font and underline (implemented as a reverse of font color / background on some terminals
            (e.g., PyCharm)
        :Getter Type: :class:`str`

        """
        return self.BOLD + self.UNDERLINE + self.YELLOW

    @property
    def announcement(self) -> str:
        return self.BOLD + self.RED + self.UNDERLINE

    @staticmethod
    def __name__() -> str:
        return "Terminal Formatter"

    def __setattr__(self, key: Any, value: Any):
        """
        Prevent setting of attributes
        """
        warn(ImmutableInstanceWarning(self), stacklevel=2)

    def __repr__(self):
        return "Terminal Formatter"

    def __call__(self, message: str, style: str) -> str:
        """
        Returns properly formatted string without setting global style

        :param message: string to be formatted
        :param style: desired format (type, emphasis, header or class var)

        :return: formatted string
        """
        # I could probably just have this fail directly, but this is a bit more graceful.
        # It's more important that the message to the user is received than raising an exception because of style
        # matters.
        if any((eq(style_, style) for style_ in dir(self) if "__" not in style_)):
            return "".join([getattr(self, style), message, self.RESET])
        else:
            return message


# instance persistent terminal scheme
TERMINAL_FORMATTER = _TerminalFormatter()
