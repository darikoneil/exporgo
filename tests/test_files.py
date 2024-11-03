import pytest

from exporgo.exceptions import MissingFilesError
from exporgo.files import MapWithDuplicates, FileSet, FileTree


class TestFileMap:
    def test_initialization(self):
        file_map = MapWithDuplicates()
        assert file_map == {}

    def test_update_dictionary_iterative(self, source):
        file_map = MapWithDuplicates()
        for file in source.rglob("*"):
            file_map.update({file.stem: file})
        assert len(file_map) == len(list(source.rglob("*")))

    def test_update_dictionary_simultaneous(self, source):
        file_map = MapWithDuplicates()
        file_map.update({str(file): file for file in source.rglob("*")})
        assert len(file_map) == len(list(source.rglob("*")))

    def test_update_key_value_pairs(self, source):
        file_map = MapWithDuplicates()
        files = [(file.stem, file) for file in source.rglob("*")]
        file_map.update(files)
        assert len(file_map) == len(list(source.rglob("*")))

    def test_update_kwargs(self, source):
        file_map = MapWithDuplicates()
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

    def test_initialization_with_index(self, tmp_path, source):
        file_tree = FileTree("source", tmp_path)
        assert file_tree.name == "source"
        assert file_tree.directory == source
        assert file_tree.num_files == len([file for file in source.rglob("*") if file.is_file()])
        assert file_tree.num_folders == len([folder for folder in source.rglob("*") if not folder.is_file()])
        assert len(file_tree) == len(list(source.glob("*")))

    def test_add_path(self, tmp_path, source):
        file_tree = FileTree("source", tmp_path)
        file_tree.add("data")
        assert isinstance(file_tree.get("data"), FileSet)
        assert file_tree.get("data").directory == tmp_path.joinpath("source").joinpath("data")

    def test_build(self, tmp_path):
        file_tree = FileTree("experiment", tmp_path)
        assert tmp_path.joinpath("experiment").exists()
        file_tree.add("data")
        file_tree.build()
        assert file_tree.get("data").directory.exists()

    def test_clear_keep(self, tmp_path, source):
        file_tree = FileTree("source", tmp_path)
        file_tree.clear(delete=False)
        assert len(file_tree) == 0
        assert tmp_path.joinpath("source").joinpath("dummy_folder_0").exists()

    def test_clear_delete(self, tmp_path, source):
        file_tree = FileTree("source", tmp_path)
        file_tree.clear(delete=True)
        assert len(file_tree) == 0
        assert not tmp_path.joinpath("source").joinpath("dummy_folder_0").exists()

    def test_get_existing_key(self, tmp_path, source):
        file_tree = FileTree("source", tmp_path)
        assert isinstance(file_tree.get("dummy_folder_0"), FileSet)

    def test_get_non_existing_key(self, tmp_path):
        file_tree = FileTree("source", tmp_path)
        with pytest.raises(KeyError):
            file_tree.get("non_existent")

    def test_pop_existing_key(self, tmp_path, source):
        file_tree = FileTree("source", tmp_path)
        file_set = file_tree.pop("dummy_folder_0")
        assert isinstance(file_set, FileSet)
        assert len(file_tree) == len(list(source.glob("*"))) - 1

    def test_pop_non_existing_key(self, tmp_path):
        file_tree = FileTree("source", tmp_path)
        with pytest.raises(KeyError):
            file_tree.pop("non_existent")

    def test_file_tree_popitem(self, tmp_path, source):
        file_tree = FileTree("source", tmp_path)
        file_set = file_tree.popitem()
        assert isinstance(file_set, FileSet)
        assert len(file_tree) == len(list(source.glob("*"))) - 1

    def test_index(self, tmp_path, source):
        file_tree = FileTree("source", tmp_path, index=False)
        file_tree.add("dummy_folder_0")
        file_tree.index()
        assert len(file_tree) == 1
        assert file_tree.num_files == 3

    def test_remap(self, tmp_path, source, destination):
        file_tree = FileTree("source", destination, index=False)
        file_tree.remap(tmp_path)
        assert file_tree.directory == tmp_path.joinpath("source")

    def test_validate_success(self, tmp_path, source):
        file_tree = FileTree("source", tmp_path)
        file_tree.validate()  # Should not raise FileNotFoundError

    def test_validate_fail(self, tmp_path, source):
        file_tree = FileTree("source", tmp_path)
        file = next(iter(file_tree.get("dummy_folder_0").files.values()))
        file.unlink()
        with pytest.raises(MissingFilesError):
            file_tree.validate()

    def test_call_with_target(self, tmp_path, source):
        file_tree = FileTree("source", tmp_path)
        target_key, target_file_set = next(iter(file_tree.items()))
        assert file_tree.get(target_key) == target_file_set

    def test_call_without_target(self, tmp_path):
        file_tree = FileTree("source", tmp_path)
        assert file_tree() == file_tree.directory

    def test_call_target_not_found(self, tmp_path):
        file_tree = FileTree("source", tmp_path)
        with pytest.raises(FileNotFoundError):
            file_tree("non_existent_file_set")
