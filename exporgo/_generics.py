from contextlib import suppress

from exporgo.organization.experiment import ExperimentRegistry, RegisteredExperiment
from exporgo.organization.pipeline import RegisteredPipeline
from exporgo.organization.step import RegisteredStep, StepRegistry

from .exceptions import DuplicateRegistrationError
from .registry import generic_function_call
from .types import Category


def generate_generic_registrations() -> None:
    generic_step_0 = RegisteredStep(
        key="generic_step_0",
        call=generic_function_call,
        file_sets="files",
        category=Category.ANALYZE,
    )
    generic_step_1 = RegisteredStep(
        key="generic_step_1",
        call=generic_function_call,
        file_sets="files",
        category=Category.ANALYZE,
    )
    pipeline = RegisteredPipeline(steps=[generic_step_0, generic_step_1])
    experiment = RegisteredExperiment(
        key="generic_experiment",
        additional_file_sets=("figures", "results"),
        pipeline=pipeline,
    )
    with StepRegistry() as registry:
        for step in (generic_step_0, generic_step_1):
            with suppress(DuplicateRegistrationError):
                registry.register(step)

    with ExperimentRegistry() as registry, suppress(DuplicateRegistrationError):
        registry.register(experiment)
