from unittest.mock import MagicMock, patch

# noinspection PyProtectedMember
from exporgo._logging import IPythonLogger, ModificationLogger


class TestIPythonLogger:
    
    @patch('exporgo._logging.get_ipython')
    def test_ipython_logger_starts_logging(self, mock_get_ipython, tmp_path):
        mock_ipython = MagicMock()
        mock_get_ipython.return_value = mock_ipython
        logger = IPythonLogger(tmp_path)
        assert logger.start_log() is True
        # noinspection PyUnresolvedReferences
        mock_ipython.run_line_magic.assert_called_with('logstart', f'-o -r -t {logger._log_file} append')

    @patch('exporgo._logging.get_ipython')
    def test_ipython_logger_check_logging(self, mock_get_ipython, tmp_path):
        mock_ipython = MagicMock()
        mock_get_ipython.return_value = mock_ipython
        logger = IPythonLogger(tmp_path)
        mock_ipython.run_line_magic.assert_called_with('logstart', f"-o -r -t {logger._log_file} append")
        logger.check_log_status()
        

    @patch('exporgo._logging.get_ipython')
    def test_ipython_logger_pauses_logging(self, mock_get_ipython, tmp_path):
        mock_ipython = MagicMock()
        mock_get_ipython.return_value = mock_ipython
        logger = IPythonLogger(tmp_path)
        assert logger.pause_log() is True
        mock_ipython.run_line_magic.assert_called_with('logstop', '')

    @patch('exporgo._logging.get_ipython')
    def test_ipython_logger_ends_logging(self, mock_get_ipython, tmp_path):
        mock_ipython = MagicMock()
        mock_get_ipython.return_value = mock_ipython
        logger = IPythonLogger(tmp_path)
        logger.end_log()
        # noinspection PyProtectedMember
        assert logger._IP is None
        mock_ipython.run_line_magic.assert_called_with('logstop', '')

class TestModificationLogger:

    def test_modification_logger_appends_with_timestamp(self):
        logger = ModificationLogger()
        logger.append('test')
        assert len(logger) == 1
        assert logger[0][0] == 'test'
        assert isinstance(logger[0][1], str)

    def test_modification_logger_extends_with_timestamp(self):
        logger = ModificationLogger()
        logger.extend(['test1', 'test2'])
        assert len(logger) == 2
        assert logger[0][0] == 'test1'
        assert logger[1][0] == 'test2'
        assert isinstance(logger[0][1], str)
        assert isinstance(logger[1][1], str)

    def test_modification_logger_loads_without_timestamp(self):
        logger = ModificationLogger()
        logger.load('test')
        assert len(logger) == 1
        assert logger[0] == 'test'