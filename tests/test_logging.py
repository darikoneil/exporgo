from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# noinspection PyProtectedMember
from exporgo._logging import IPythonLogger, ModificationLogger, get_timestamp


@patch('exporgo._logging.get_ipython')
def ipython_logger_starts_logging(mock_get_ipython):
    mock_ipython = MagicMock()
    mock_get_ipython.return_value = mock_ipython
    logger = IPythonLogger(Path('/path/to/logs'))
    assert logger.start_log() is True
    mock_ipython.run_line_magic.assert_called_with('logstart', '-o -r -t /path/to/logs/log_file.log append')

@patch('exporgo._logging.get_ipython')
def ipython_logger_pauses_logging(mock_get_ipython):
    mock_ipython = MagicMock()
    mock_get_ipython.return_value = mock_ipython
    logger = IPythonLogger(Path('/path/to/logs'))
    assert logger.pause_log() is True
    mock_ipython.run_line_magic.assert_called_with('logstop', '')

@patch('exporgo._logging.get_ipython')
def ipython_logger_ends_logging(mock_get_ipython):
    mock_ipython = MagicMock()
    mock_get_ipython.return_value = mock_ipython
    logger = IPythonLogger(Path('/path/to/logs'))
    logger.end_log()
    assert logger._IP is None
    mock_ipython.run_line_magic.assert_called_with('logstop', '')

def modification_logger_appends_with_timestamp():
    logger = ModificationLogger()
    logger.append('test')
    assert len(logger) == 1
    assert logger[0][0] == 'test'
    assert isinstance(logger[0][1], str)

def modification_logger_extends_with_timestamp():
    logger = ModificationLogger()
    logger.extend(['test1', 'test2'])
    assert len(logger) == 2
    assert logger[0][0] == 'test1'
    assert logger[1][0] == 'test2'
    assert isinstance(logger[0][1], str)
    assert isinstance(logger[1][1], str)

def modification_logger_loads_without_timestamp():
    logger = ModificationLogger()
    logger.load('test')
    assert len(logger) == 1
    assert logger[0] == 'test'