import os
import subprocess
import sys
from pathlib import Path

import pytest
import toml

# noinspection PyProtectedMember
from exporgo._color import TERMINAL_FORMATTER


def retrieve_details(path):
    details = toml.load(path).get("project")
    name = details.get("name")
    version = details.get("version")
    dependencies = details.get("dependencies")
    return name, version, dependencies


def retrieve_project_directory(path):
    return Path(path).parent


def retrieve_project_file():
    project_file = os.path.join(os.getcwd(), "pyproject.toml")
    if not os.path.exists(project_file):
        project_file = os.path.join(Path(os.getcwd()).parent, "pyproject.toml")
    if not os.path.exists(project_file):
        raise FileNotFoundError("Can't find project file")
    return project_file


def collect_project():
    project_file = retrieve_project_file()
    project_directory = retrieve_project_directory(project_file)
    package_name, package_version, package_dependencies = retrieve_details(project_file)
    return (
        project_directory,
        project_file,
        package_name,
        package_version,
        package_dependencies,
    )


# get project information and work from correct directory
proj_dir, proj_file, pkg_name, pkg_version, pkg_dependencies = collect_project()
os.chdir(proj_dir)


print(
    TERMINAL_FORMATTER("\nPackage: ", "emphasis")
    + TERMINAL_FORMATTER(f"{pkg_name}", "type")
)
print(TERMINAL_FORMATTER(f"Version: ", "emphasis") + f"{pkg_version}")
print(TERMINAL_FORMATTER(f"Dependencies: ", "emphasis") + f"{pkg_dependencies}")


@pytest.mark.parametrize("path", [proj_dir])
def test_install(path):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-e ."])
    except subprocess.CalledProcessError as e:
        print(f"{e.output}")
        # This doesn't work on non-windows systems, but we don't support those anyway.
