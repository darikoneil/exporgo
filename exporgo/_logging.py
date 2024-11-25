import warnings
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

# noinspection PyProtectedMember
from IPython import get_ipython


class IPythonLogger:
    """
    Wrapper class for IPython logging
    """

    def __init__(self, directory: Path, start: bool = True):
        """
        Wrapper class for IPython logging

        :param directory: Path to the directory where the log file will be stored

        :param start: If True, the logging will start immediately
        """
        #: bool: running status
        self._running = False

        #: object: IPython magic
        self._IP = None

        #: pathlib.Path: path to log file
        self._log_file = directory.joinpath("log.txt")

        if directory.exists() and not self._log_file.exists():
            self._create_log()

        if start:
            self.start()

    def running(self) -> bool:
        """
        Returns the running status

        :return: True if running, False otherwise
        """
        return self._running

    def status(self) -> None:
        """
        Checks log status
        """

        self._IP.run_line_magic('logstate', '')

    def pause(self) -> bool:
        """
        Pause the logging

        :return True if logging is paused, False otherwise
        """
        # with warnings.catch_warnings(): I don't think this is necessary anymore, but leaving here for now
        warnings.simplefilter("error")
        try:
            self._IP.run_line_magic('logstop', '')
        except AttributeError:
            pass  # technically not great, but sometimes we might end up calling this twice and if it's already
            # stopped, it will throw an error, and we don't ever care about that
        except UserWarning as e:  # pragma: no cover
            print(e)  # because it's not my problem if ipython fails, so no coverage. not even sure how to test this
            return False
        self._running = False
        return True

    def end(self) -> None:
        """
        Ends the logging
        """
        self.pause()
        self._IP = None

    def start(self) -> bool:
        """
        Starts the logging

        :return: True if logging is started, False otherwise
        """
        self._IP = get_ipython()
        _magic_arguments = '-o -r -t ' + str(self._log_file) + ' append'
        # with warnings.catch_warnings(): I don't think this is necessary anymore, but leaving here for now
        warnings.simplefilter("error")
        try:
            self._IP.run_line_magic('logstart', _magic_arguments)
        except AttributeError:
            pass  # technically not great, but sometimes we might end up calling this twice and if it's already
            # stopped, it will throw an error, and we don't ever care about that
        except UserWarning as e:  # pragma: no cover
            print(e)  # because it's not my problem if ipython fails, so no coverage. not even sure how to test this
            return False
        self._running = True
        return True

    def _create_log(self) -> None:
        """
        Creates a log file for a new instance
        """
        with open(self._log_file, "w") as log:
            log.write("")


class ModificationLogger(deque):
    """
    A logger class that extends deque to log modifications with timestamps.
    """

    def append(self, __x: Any) -> None:
        """
        Append an item to the right end of the deque with a timestamp.

        :param __x: The item to append
        """
        __x = (__x, get_timestamp())
        super().append(__x)

    # noinspection SpellCheckingInspection
    def appendleft(self, __x: Any) -> None:
        """
        Append an item to the left end of the deque with a timestamp.

        :param __x: The item to append
        """
        __x = (__x, get_timestamp())
        super().appendleft(__x)

    def extend(self, __iterable: Iterable[Any]) -> None:
        """
        Extend the right end of the deque by appending elements from the iterable with timestamps.

        :param __iterable: An iterable of items to append
        """
        for iter_ in __iterable:
            self.append(iter_)

    # noinspection SpellCheckingInspection
    def extendleft(self, __iterable: Iterable[Any]) -> None:  # pragma: no cover
        """
        Extend the left end of the deque by appending elements from the iterable with timestamps.

        :param __iterable: An iterable of items to append
        """
        # not covered because it's never used, but it's here for completeness
        for iter_ in __iterable:
            self.appendleft(iter_)

    def load(self, value: Any) -> None:
        """
        Load a value to the left end of the deque without a timestamp.

        :param value: The value to load
        """
        super().appendleft(value)


def get_timestamp() -> str:
    """
    Uses datetime to return date/time str. Simply a function to guarantee consistency

    :return: current date and time
    """
    return datetime.now().strftime("%m-%d-%Y %H:%M:%S")
