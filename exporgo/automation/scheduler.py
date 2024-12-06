import subprocess
from pathlib import Path


class Scheduler:
    def __init__(self, config):
        self.config = config
        self._tmp = Path.cwd().joinpath("tmp")
        self._tmp.mkdir()
        self.file= None
        self.task = ""

    def create(self):
        ...

    def delete(self):
        ...

    def _cli_execute(self):
        cmd = ['schtasks', '/create', '/xml', self.file, '/tn', self.config]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout, result.stderr

    def _serialize_task(self):
        ...

    # noinspection PyMethodMayBeStatic
    def _create_task(self):
        ...
