from .registry.experiments import ExperimentConfig
from .registry.pipelines import AnalysisConfig, PipelineConfig
import json
from pathlib import Path

def update_json_schema() -> None:
    """
    Update JSON schema references
    """

    def to_snake_case(name: str) -> str:
        return "".join(f"_{char.lower()}" if char.isupper() else char for char in name)[1:]

    path = Path(__file__).parent.joinpath("schemas")

    for model in (AnalysisConfig, PipelineConfig, ExperimentConfig):
        with path.joinpath(f"{to_snake_case(model.__name__)}.json").open("w") as file:
            # noinspection PyTypeChecker
            json.dump(model.model_json_schema(), file, indent=4, sort_keys=False)
