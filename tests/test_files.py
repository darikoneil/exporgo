import pytest
from exporgo.files import FileMap, FileSet, FileTree


class TestFileMap:
    def test_initialization(self):
        file_map = FileMap()
        assert file_map == {}

    def test_update_dictionary_iterative(self, source):
        file_map = FileMap()
        for file in source.rglob("*"):
            file_map.update({file.stem: file})
        assert len(file_map) == len(list(source.rglob("*")))

    def test_update_dictionary_simultaneous(self, source):
        file_map = FileMap()
        file_map.update({str(file): file for file in source.rglob("*")})
        assert len(file_map) == len(list(source.rglob("*")))

    def test_update_key_value_pairs(self, source):
        file_map = FileMap()
        files = [(file.stem, file) for file in source.rglob("*")]
        file_map.update(files)
        assert len(file_map) == len(list(source.rglob("*")))

    def test_update_kwargs(self, source):
        file_map = FileMap()
        file_map.update(**{str(file): file for file in source.rglob("*")})
        assert len(file_map) == len(list(source.rglob("*")))


class TestFileSet:
    def test_initialization_no_index(self, tmp_path, source):
        file_set = FileSet("source", tmp_path, index=False)
        assert file_set._name == "source"
        assert file_set.directory == source
        assert file_set.files == {}
        assert file_set.folders == {}

    def test_initialization_with_index(self, tmp_path, source):
        file_set = FileSet("source", tmp_path, index=True)
        assert file_set._name == "source"
        assert file_set.directory == source
        assert len(file_set.files) == len([file for file in source.rglob("*") if file.is_file()])
        assert len(file_set.folders) == len([folder for folder in source.rglob("*") if not folder.is_file()])

    def test_find_file_type(self, tmp_path, source):
        file_set = FileSet("source", tmp_path)
        txt_files = file_set.find_file_type(".txt")
        assert all(file.suffix == ".txt" for file in txt_files)
        assert len(txt_files) == len([file for file in source.rglob("*") if file.suffix == ".txt"])

    def test_find_matching_files(self, tmp_path, source):
        file_set = FileSet("source", tmp_path)
        matching_files = file_set.find_matching_files("*file_0.txt")
        assert all(file.match("dummy_file_0.txt") for file in matching_files)
        assert len(matching_files) == len([file for file in source.rglob("*") if file.match("dummy_file_0.txt")])

    def test_remap(self, tmp_path, source, destination):
        file_set = FileSet("source", destination)
        file_set.remap(tmp_path)
        assert file_set.directory == source

    def test_validate_pass(self, tmp_path, source):
        file_set = FileSet("source", tmp_path)
        file_set.validate()

    def test_validate_fail(self, tmp_path, source):
        file_set = FileSet("source", tmp_path)
        file = next(iter(file_set.files.values()))
        file.unlink()
        with pytest.raises(FileNotFoundError):
            file_set.validate()

    def test_call_with_target_file(self, tmp_path, source):
        file_set = FileSet("source", tmp_path)
        target_key, target_file = next(iter(file_set.files.items()))
        assert file_set(target_key) == target_file

    def test_call_with_target_folder(self, tmp_path, source):
        file_set = FileSet("source", tmp_path)
        target_key, target_folder = next(iter(file_set.folders.items()))
        assert file_set(target_key) == target_folder

    def test_call_without_target(self, tmp_path, source):
        file_set = FileSet("source", tmp_path)
        assert file_set() == file_set.directory
        assert file_set() == source

    def test_call_target_not_found(self, tmp_path, source):
        file_set = FileSet("source", tmp_path)
        with pytest.raises(FileNotFoundError):
            file_set("non_existent_file")


class TestFileTree:
    ...

