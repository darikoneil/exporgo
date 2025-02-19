from dataclasses import dataclass
from operator import eq

__all__ = ["TERMINAL_FORMATTER"]


@dataclass(frozen=True)
class _TerminalFormatter:
    """
    A container class for exporgo's terminal printing color/font scheme. This class is immutable and should not be
    modified. It is intended to be used as a singleton instance, and is not intended to be instantiated more than once.
    I mean, you can, but it's not going to do anything for you. It's just going to be a waste of memory.
    """

    YELLOW: str = "\u001b[38;5;11m"
    GREEN: str = "\033[38;2;64;204;139m"
    ORANGE: str = "\033[38;2;253;174;97m"
    RED: str = "\033[38;2;255;78;75m"
    BLUE: str = "\033[38;2;15;159;255m"
    BOLD: str = "\u001b[1m"
    UNDERLINE: str = "\u001b[7m"
    RESET: str = "\033[0m"

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
        """
        :Getter: Red font style for critical announcements
        :Getter Type: :class:`str`
        """
        return self.BOLD + self.RED + self.UNDERLINE

    @staticmethod
    def __name__() -> str:
        return "Terminal Formatter"

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
