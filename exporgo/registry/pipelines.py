from typing import Sequence
from pydantic import BaseModel, Field

from .config import MODEL_CONFIG
from ..registry.steps import StepConfig
from .._tools import check_if_string_set


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Pipeline Configuration for Combinatorial Experiment Functionality
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""

class PipelineConfig(BaseModel):
    steps: StepConfig | Sequence[StepConfig] = Field(None, title="Sequence of steps in the pipeline")
    model_config = MODEL_CONFIG

    @property
    def file_sets(self) -> set[str]:
        return {file_set for step in self.steps for file_set in check_if_string_set(step.file_sets)}
