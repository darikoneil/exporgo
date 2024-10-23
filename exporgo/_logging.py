from __future__ import annotations

import warnings
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

# noinspection PyProtectedMember
from IPython import get_ipython

from ._validators import convert_permitted_types_to_required


@convert_permitted_types_to_required(permitted=(str, Path), required=Path, pos=0, key="directory")
class IPythonLogger:
    """
    Wrapper class for IPython logging
    """

    def __init__(self, directory: Path):
        """
        Wrapper class for IPython logging

        :param directory: Path to the directory where the log file will be stored
        """

        #: object: IPython magic
        self._IP = None

        #: pathlib.Path: path to log file
        self._log_file = directory.joinpath("log_file.log")

        if directory.exists() and not self._log_file.exists():
            self._create_log()

        self.start_log()

    def check_log_status(self) -> None:
        """
        Checks log status
        """

        self._IP.run_line_magic('logstate', '')

    def pause_log(self) -> bool:
        """
        Pause the logging

        :return True if logging is paused, False otherwise
        """
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            try:
                self._IP.run_line_magic('logstop', '')
            except UserWarning as e:
                print(e)
                return False
        return True

    def end_log(self) -> None:
        """
        Ends the logging
        """
        self.pause_log()
        self._IP = None

    def start_log(self) -> bool:
        """
        Starts the logging

        :return: True if logging is started, False otherwise
        """
        self._IP = get_ipython()
        _magic_arguments = '-o -r -t ' + str(self._log_file) + ' append'
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            try:
                self._IP.run_line_magic('logstart', _magic_arguments)
            except UserWarning as e:
                print(e)
                return False
        return True

    def _create_log(self) -> None:
        """
        Creates a log file for a new instance
        """
        with open(self._log_file, "w") as log:
            log.write("")

    def __json_decode__(self, **attrs):
        """
        Decode JSON attributes to initialize the logger.

        :param attrs: JSON attributes
        """
        directory = attrs.get("_log_file").parent
        self.__init__(directory)
        # TODO: Necessary?


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
            iter_ = (iter_, get_timestamp())
            self.append(iter_)

    # noinspection SpellCheckingInspection
    def extendleft(self, __iterable: Iterable[Any]) -> None:
        """
        Extend the left end of the deque by appending elements from the iterable with timestamps.

        :param __iterable: An iterable of items to append
        """
        for iter_ in __iterable:
            iter_ = (iter_, get_timestamp())
            self.appendleft(iter_)

    def load(self, value: Any) -> None:
        """
        Load a value to the left end of the deque without a timestamp.

        :param value: The value to load
        """
        super().appendleft(value)

    def __json_encode__(self):
        """
        Encode the deque values to a JSON serializable format.

        :return: A dictionary with the deque values
        """
        return {"values": list(self)}

    def __json_decode__(self, **attrs):
        """
        Decode JSON attributes to load the deque.

        :param attrs: JSON attributes containing the values to load
        """
        for value in attrs.get("values"):
            self.load(tuple(value))


def get_timestamp() -> str:
    """
    Uses datetime to return date/time str. Simply a function to guarantee consistency

    :return: current date and time
    """
    return datetime.now().strftime("%m-%d-%Y %H:%M:%S")
