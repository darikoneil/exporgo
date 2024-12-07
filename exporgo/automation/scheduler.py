import subprocess
from pathlib import Path
from task import Task
from ..tools import convert, write_xml
from ..types import File

__all__ = ["schedule_task"]


def _construct_temporary_file(name: str) -> Path:
    temporary_directory = Path.cwd().joinpath("tmp")
    temporary_directory.mkdir(exist_ok=True)
    temporary_file = temporary_directory.joinpath(name).with_suffix(".xml")
    return temporary_file


@convert(parameter="file", permitted=(File, ), required=str)
def _add_to_scheduler(name: str, file: File) -> bool:
    command = ['schtasks', '/create', '/tn', name, '/xml', file]
    result = subprocess.run(command, timeout=60, check=True, capture_output=True, text=True)
    return result.returncode == 0


def schedule_task(task: Task) -> bool:
    name = task.registration_info.name
    file = _construct_temporary_file(name)
    write_xml(file, task.model_dump_xml())
    return _add_to_scheduler(name, file)
