from functools import partial
from pathlib import Path
from shutil import copy2
from tkinter import Tk
from tkinter.filedialog import askdirectory, askopenfilename
from typing import Optional

from joblib import Parallel, delayed
from tqdm import tqdm

from ._validators import convert_permitted_types_to_required

"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// User Interactions
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


def select_file(**kwargs) -> Path:
    """
    Interactive tool for file selection. All keyword arguments are
    passed to `tkinter.filedialog.askopenfilename <https://docs.python.org/3/library/tk.html>`_

    :param kwargs: keyword arguments passed to tkinter.filedialog.askdirectory

    :raises: FileNotFoundError if file not found

    :return: absolute path to file
    """
    root = Tk()
    file_path = Path(askopenfilename(**kwargs))

    if file_path == ".":
        raise FileNotFoundError(f"File not found: {file_path}")

    root.destroy()

    return file_path.resolve()


def select_directory(**kwargs) -> Path: # pragma: no cover
    """
    Interactive tool for directory selection. All keyword arguments are
    passed to `tkinter.filedialog.askdirectory <https://docs.python.org/3/library/tk.html>`_

    :param kwargs: keyword arguments passed to tkinter.filedialog.askdirectory

    :raises: IOError if directory not found

    :return: absolute path to directory
    """
    root = Tk()
    directory_path = Path(askdirectory(**kwargs))

    if directory_path == ".":
        raise IOError(f"Directory not found: {directory_path}")

    root.destroy()

    return directory_path.resolve()


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// File Operations
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


@convert_permitted_types_to_required(permitted=(str, Path), required=Path, pos=0, key="source")
@convert_permitted_types_to_required(permitted=(str, Path), required=Path, pos=1, key="destination")
def verbose_copy(source: str | Path,
                 destination: str | Path,
                 feedback: Optional[str] = None) -> bool:
    """
    Copy a file from source to destination. If verbose is True, print feedback.

    :param source: source file path
    :type source: :class:`str` or :class:`Path <pathlib.Path>`

    :param destination: destination file path
    :type destination: :class:`str` or :class:`Path <pathlib.Path>`

    :param feedback: feedback message
    :type feedback: :class:`Optional <typing.Optional>`\[:class:`str`\], default: ``None``

    :return: True if successful, False otherwise
    """
    # Verbose, performant copying by parallelizing the copy operation. This is faster than the built-in shutil.copytree.
    # Implemented by making a partial containing the source & destination paths, and the fast-copy function for the OS.
    # Joblib will handle the parallelization when provided the partial via 'delayed'. Loky seems to be the fastest for
    # moving many small files, but threading could be faster in other scenarios. I don't see a user providing enough
    # file paths they run out of system RAM, so not exposing the joblib backend to allow threading as an alternative.
    # The list of the file paths is wrapped in tqdm to provide verbose feedback (progress bar).

    def _copy(source_: Path, destination_: Path, file: Path) -> Path: # pragma: no cover
        """
        Copy a file from source to destination (single file function, parallelized). Should call the system fast-copy
        regardless of the OS.
        """
        file_destination = destination_.joinpath(file.relative_to(source_))
        return copy2(file, file_destination)

    destination.mkdir(parents=True, exist_ok=True)
    folders = [folder for folder in source.rglob("*") if not folder.is_file()]
    destination.mkdir(parents=True, exist_ok=True)
    for folder in folders:
        destination_folder = destination.joinpath(folder.relative_to(source))
        destination_folder.mkdir(parents=True, exist_ok=True)

    files = [file for file in source.rglob("*") if file.is_file()]
    copier = partial(_copy, source, destination)
    message = f"Copying {feedback} files" if feedback else "Copying files"
    return all(Parallel(n_jobs=-1, backend="loky")(delayed(copier)(file) for file in tqdm(files,
                                                                                          total=len(files),
                                                                                          desc=message)))
