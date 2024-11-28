from exporgo.files import FileTree


def prepare_function(file_tree: FileTree) -> None:
    file = next(file_tree.get("files").find("*dummy_data_0.csv"))
    # data
    save_location = file_tree.get("files").directory.joinpath("prepared_dummy_data_0.csv")
    # save data


def analyze_function(file_tree: FileTree) -> None:
    file = next(file_tree.get("files").find("*prepared_dummy_data_0.csv"))
    # data
    save_location = file_tree.get("results").directory.joinpath("analyzed_dummy_data_0.csv")
    # save data


def summarize_function(file_tree: FileTree) -> None:
    file = next(file_tree.get("results").find("*analyzed_dummy_data_0.csv"))
    # data
    save_location = file_tree.get("results").directory.joinpath("summarized_dummy_data_0.csv")
    # save data
