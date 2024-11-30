import pytest

from exporgo.exceptions import MissingFilesError
from exporgo.files import DictWithDuplicates, FileSet, FileTree


class TestDictWithDuplicates:
    def test_initialization(self):
        file_map = DictWithDuplicates()
        assert file_map == {}

    def test_update_dictionary_iterative(self, simple_source):
        file_map = DictWithDuplicates()
        for file in simple_source.rglob("*"):
            file_map.update({file.stem: file})
        assert len(file_map) == len(list(simple_source.rglob("*")))

    def test_update_dictionary_simultaneous(self, simple_source):
        file_map = DictWithDuplicates()
        file_map.update({str(file): file for file in simple_source.rglob("*")})
        assert len(file_map) == len(list(simple_source.rglob("*")))

    def test_update_key_value_pairs(self, simple_source):
        file_map = DictWithDuplicates()
        files = [(file.stem, file) for file in simple_source.rglob("*")]
        file_map.update(files)
        assert len(file_map) == len(list(simple_source.rglob("*")))

    def test_update_kwargs(self, simple_source):
        file_map = DictWithDuplicates()
        file_map.update(**{str(file): file for file in simple_source.rglob("*")})
        assert len(file_map) == len(list(simple_source.rglob("*")))


class TestFileSet:
    def test_initialization_no_index(self, tmp_path, simple_source):
        file_set = FileSet("source", tmp_path, index=False)
        assert file_set._name == "source"
        assert file_set.directory == simple_source
        assert file_set.files == {}
        assert file_set.folders == {}

    def test_initialization_with_index(self, tmp_path, simple_source):
        file_set = FileSet("source", tmp_path, index=True)
        assert file_set._name == "source"
        assert file_set.directory == simple_source
        assert len(file_set.files) == len([file for file in simple_source.rglob("*") if file.is_file()])
        assert len(file_set.folders) == len([folder for folder in simple_source.rglob("*") if not folder.is_file()])

    def test_find_file_type(self, tmp_path, simple_source):
        file_set = FileSet("source", tmp_path)
        txt_files = list(file_set.find("*.txt"))
        assert all(file.suffix == ".txt" for file in txt_files)
        assert len(txt_files) == len([file for file in simple_source.rglob("*") if file.suffix == ".txt"])

    def test_find_matching_files(self, tmp_path, simple_source):
        file_set = FileSet("source", tmp_path)
        matching_files = list(file_set.find("*file_0.txt"))
        assert all(file.match("dummy_file_0.txt") for file in matching_files)
        assert len(list(matching_files)) == len([file for file in simple_source.rglob("*") if file.match("dummy_file_0.txt")])

    def test_remap(self, tmp_path, simple_source, destination):
        file_set = FileSet("source", destination)
        file_set.remap(tmp_path)
        assert file_set.directory == simple_source

    def test_validate_pass(self, tmp_path, simple_source):
        file_set = FileSet("source", tmp_path)
        file_set.validate()

    def test_validate_fail(self, tmp_path, simple_source):
        file_set = FileSet("source", tmp_path)
        file = next(iter(file_set.files.values()))
        file.unlink()
        with pytest.raises(FileNotFoundError):
            file_set.validate()

    def test_call_with_target_file(self, tmp_path, simple_source):
        file_set = FileSet("source", tmp_path)
        target_key, target_file = next(iter(file_set.files.items()))
        assert file_set(target_key) == target_file

    def test_call_with_target_folder(self, tmp_path, simple_source):
        file_set = FileSet("source", tmp_path)
        target_key, target_folder = next(iter(file_set.folders.items()))
        assert file_set(target_key) == target_folder

    def test_call_without_target(self, tmp_path, simple_source):
        file_set = FileSet("source", tmp_path)
        assert file_set() == file_set.directory
        assert file_set() == simple_source

    def test_call_target_not_found(self, tmp_path, simple_source):
        file_set = FileSet("source", tmp_path)
        with pytest.raises(FileNotFoundError):
            file_set("non_existent_file")


class TestFileTree:

    def test_initialization_with_index(self, tmp_path, simple_source):
        file_tree = FileTree(tmp_path.joinpath("source"))
        assert file_tree.tree_directory == tmp_path.joinpath("source")
        assert file_tree.parent_directory == tmp_path
        assert file_tree.num_files == len([file for file in simple_source.rglob("*") if file.is_file()])
        assert file_tree.num_folders == len([folder for folder in simple_source.rglob("*") if not folder.is_file()])
        assert len(file_tree) == len(list(simple_source.glob("*")))

    def test_add_path(self, tmp_path, simple_source):
        file_tree = FileTree(tmp_path.joinpath("source"))
        file_tree.add("data")
        assert isinstance(file_tree.get("data"), FileSet)
        assert file_tree.get("data").directory == tmp_path.joinpath("source").joinpath("data")

    def test_build(self, tmp_path):
        file_tree = FileTree(tmp_path.joinpath("experiment"))
        tmp_path.joinpath("experiment").mkdir(parents=True, exist_ok=True)
        file_tree.add("data")
        file_tree.build(None)
        assert tmp_path.joinpath("experiment").exists()
        assert file_tree.get("data").directory.exists()

    def test_clear_keep(self, tmp_path, simple_source):
        file_tree = FileTree(tmp_path.joinpath("source"))
        file_tree.clear(delete=False)
        assert len(file_tree) == 0
        assert tmp_path.joinpath("source").joinpath("dummy_folder_0").exists()

    def test_clear_delete(self, tmp_path, simple_source):
        file_tree = FileTree(tmp_path.joinpath("source"))
        file_tree.clear(delete=True)
        assert len(file_tree) == 0
        assert not tmp_path.joinpath("source").joinpath("dummy_folder_0").exists()

    def test_get_existing_key(self, tmp_path, simple_source):
        file_tree = FileTree(tmp_path.joinpath("source"))
        assert isinstance(file_tree.get("dummy_folder_0"), FileSet)

    def test_get_non_existing_key(self, tmp_path):
        file_tree = FileTree(tmp_path.joinpath("source"))
        with pytest.raises(KeyError):
            file_tree.get("non_existent")

    def test_pop_existing_key(self, tmp_path, simple_source):
        file_tree = FileTree(tmp_path.joinpath("source"))
        file_set = file_tree.pop("dummy_folder_0")
        assert isinstance(file_set, FileSet)
        assert len(file_tree) == len(list(simple_source.glob("*"))) - 1

    def test_pop_non_existing_key(self, tmp_path):
        file_tree = FileTree(tmp_path.joinpath("source"))
        with pytest.raises(KeyError):
            file_tree.pop("non_existent")

    def test_file_tree_popitem(self, tmp_path, simple_source):
        file_tree = FileTree(tmp_path.joinpath("source"))
        file_set = file_tree.popitem()
        assert isinstance(file_set, FileSet)
        assert len(file_tree) == len(list(simple_source.glob("*"))) - 1

    def test_populate(self, tmp_path, simple_source):
        file_tree = FileTree(tmp_path.joinpath("source"), populate=False)
        file_tree.add("dummy_folder_0")
        file_tree.index()
        assert len(file_tree) == 1
        assert file_tree.num_files == 3

    def test_remap(self, tmp_path, simple_source, destination):
        file_tree = FileTree(simple_source, destination, populate=False)
        file_tree.remap(tmp_path)
        assert file_tree.parent_directory == tmp_path

    def test_validate_success(self, tmp_path, simple_source):
        file_tree = FileTree(tmp_path.joinpath("source"))
        file_tree.validate()  # Should not raise FileNotFoundError

    def test_validate_fail(self, tmp_path, simple_source):
        file_tree = FileTree(tmp_path.joinpath("source"))
        file = next(iter(file_tree.get("dummy_folder_0").files.values()))
        file.unlink()
        with pytest.raises(MissingFilesError):
            file_tree.validate()

    def test_call_with_target(self, tmp_path, simple_source):
        file_tree = FileTree(tmp_path.joinpath("source"))
        target_key, target_file_set = next(iter(file_tree.items()))
        assert file_tree.get(target_key) == target_file_set

    def test_call_without_target(self, tmp_path):
        file_tree = FileTree(tmp_path.joinpath("source"))
        assert file_tree() == file_tree.tree_directory

    def test_call_target_not_found(self, tmp_path):
        file_tree = FileTree(tmp_path.joinpath("source"))
        with pytest.raises(FileNotFoundError):
            file_tree("non_existent_file_set")
