from typing import Callable, Any
from functools import update_wrapper
from types import MappingProxyType


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