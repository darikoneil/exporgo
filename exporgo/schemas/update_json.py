from pathlib import Path
import json
from ..registry import AnalysisConfig, ExperimentConfig
from ..registry import ExporgoSettings


def _update_json_schema() -> None:
    """
    Update JSON schema references
    """

    def to_snake_case(name: str) -> str:
        return "".join(f"_{char.lower()}" if char.isupper() else char for char in name)[1:]

    path = Path(__file__).parent

    for model in (AnalysisConfig, ExperimentConfig, ExporgoSettings):
        with path.joinpath(f"{to_snake_case(model.__name__)}.json").open("w") as file:
            # noinspection PyTypeChecker
            json.dump(model.model_json_schema(), file, indent=4, sort_keys=False)


if __name__ == "__main__":
    _update_json_schema()
