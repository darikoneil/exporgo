import subprocess

import pytest

from exporgo.__main__ import execute_exporgo
from exporgo.organization.subject import Subject


class TestEntryPoint:
    test_name = "entry_test"
    test_base_directory = None
    test_file = None

    @pytest.fixture(scope="function", autouse=True)
    def setup_test(self, entry_point, tmp_path):
        self.test_base_directory = tmp_path
        test_subject = Subject(name=self.test_name,
                               directory=self.test_base_directory)
        test_subject.save()
        self.test_file = test_subject.directory.joinpath("organization.yaml")
        self.input_arguments = "python -m " + entry_point + " " + str(self.test_file)

    def test_entry_point_process(self) -> None:
        self.test_file.exists()
        process = subprocess.Popen(self.input_arguments,
                                   stdout=subprocess.PIPE,
                                   text=True)
        stdout, stderr = process.communicate()

    def test_entry_point_local(self) -> None:
        self.test_file.exists()
        execute_exporgo(self.test_file)
