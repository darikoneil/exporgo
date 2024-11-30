import csv
from pathlib import Path
from typing import Iterable

from exporgo.files import FileTree
from tests.conftest import RAW_FILENAME, RESULTS_FILENAME


def load_data(file_path: Path) -> tuple[list[str], Iterable]:
    data = []
    with open(file_path, mode='r', newline='') as file:
        reader = csv.reader(file)
        header = next(reader)  # Read the header
        for row in reader:
            data.append(row)
    return header, data


def save_data(header: list[str], data: Iterable, save_location: Path):
    with open(save_location, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(data)


def prepare_function(file_tree: FileTree) -> None:
    file = next(file_tree.find(f"*{RAW_FILENAME}"))
    header, data = load_data(file)
    header.append("Prepared Signal")
    data = [[int(x), float(y), float(y) * -1 if float(y) < 0.0 else float(y)] for x, y in data]
    save_data(header, data, file_tree.get("results").directory.joinpath(RESULTS_FILENAME))


def analyze_function(file_tree: FileTree) -> None:
    file = next(file_tree.get("results").find(f"*{RESULTS_FILENAME}"))
    header, data = load_data(file)
    header.append("Analyzed Signal")
    data = [[int(x), float(y), float(z), float(y) * 2] for x, y, z in data]
    save_data(header, data, file)


def summarize_function(file_tree: FileTree) -> None:
    file = next(file_tree.get("results").find(f"*{RESULTS_FILENAME}"))
    header, data = load_data(file)
    header.append("Summarized Signal")
    data = [[int(x), float(y), float(z), float(a), 1 if float(z) > float(a) else -1] for x, y, z, a in data]
    save_data(header, data, file)
