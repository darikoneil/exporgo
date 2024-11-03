from functools import update_wrapper
from types import MappingProxyType
from typing import Any, Callable, Iterable, Generator
from .registry.experiments import ExperimentConfig
from .registry.pipelines import PipelineConfig, AnalysisConfig
from pathlib import Path
import json


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Conditional Dispatcher
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


def _find_implementation(registry: dict, *args: Any, **kwargs: Any) -> Callable:
    for condition, function in reversed(registry.items()):
        try:
            if condition(*args, **kwargs):
                return function
        except TypeError:
            pass


# noinspection PyUnusedLocal
def _always_true(*args: Any, **kwargs: Any):
    return True


def conditional_dispatch(func: Callable) -> Callable:
    """
    Conditional-dispatch generic function decorator that transforms a function into a generic function whose behavior is
    defined by registered (arbitrary) conditional statements.

    """
    # implementation registry
    registry = {}

    def dispatch(*args: Any, **kwargs: Any) -> Callable:
        """
        Runs the dispatch algorithm to return the best available implementation
        for the given conditionals registered on the function.

        """
        return _find_implementation(registry, *args, **kwargs)

    def register(conditional: Callable, function: Callable = None) -> Callable:
        if function is None:
            return lambda f: register(conditional, f)
        else:
            registry[conditional] = function
        return function

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not args:
            raise TypeError(f'{funcname} requires at least '
                            '1 positional argument')
        return dispatch(*args, **kwargs)(*args, **kwargs)

    funcname = getattr(func, '__name__', 'conditional_dispatch function')
    registry[_always_true] = func
    wrapper.register = register
    wrapper.dispatch = dispatch
    wrapper.registry = MappingProxyType(registry)
    update_wrapper(wrapper, func)
    return wrapper


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Miscellaneous Tools
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""

def unique_generator(iterable: Iterable) -> Generator[Any, None, None]:
    """
    Generator that yields only the unique elements from an iterable. This isn't memory efficient because we
    keep a set of all the elements we've seen so far (which has more overhead than a simple list due to the hashing),
    but it's lazier than the alternative of grabbing everything at once--especially if we don't plan on using
    everything.
    """
    unique = set()
    for item in iterable:
        if item not in unique:
            unique.add(item)
            yield item


def check_if_string_set(iterable: Iterable) -> set:
    """
    Checks if an iterable is simply a string when constructing a set. This is useful for ensuring that we don't
    accidentally create a set of characters when we really wanted a set of strings.
    """
    return {iterable, } if isinstance(iterable, str) else set(iterable)


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
