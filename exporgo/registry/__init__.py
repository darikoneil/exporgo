from pathlib import Path

#: pathlib.Path: path to registry directory
_REGISTRY_PATH = Path(__file__).parent

#: pathlib.Path: path to experiments registry
PATH_EXPERIMENTS = _REGISTRY_PATH.joinpath("registered_experiments.json")

#: pathlib.Path: path to steps registry
PATH_STEPS = _REGISTRY_PATH.joinpath("registered_steps.json")


def generic_function_call(*args, **kwargs) -> None:
    """
    Generic function call for testing purposes only. Why am I here? Because it will be found by the test suite if it is
    with other testing assets.
    """
    print(f"generic_function_call({args=}, {kwargs=})")
