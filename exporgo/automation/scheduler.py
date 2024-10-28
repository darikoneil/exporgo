from pathlib import Path
import subprocess


class Scheduler:
    def __init__(self, config):
        self.config = config
        self._tmp = Path.cwd().joinpath("tmp")
        self._tmp.mkdir()
        self.file = self._tmp.joinpath("task.xml")
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
        with open(self.file, "w", encoding="UTF-16") as file:
            file.write(self.task)

    def _create_task(self):
        xml = ""
        return xml
