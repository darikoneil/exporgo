import inspect
from contextlib import suppress
from functools import update_wrapper, wraps
from inspect import getsourcefile
from types import MappingProxyType
from typing import Any, Callable, Generator, Iterable, Optional
from xml.dom.minidom import parseString
from xml.etree.ElementTree import Element, tostring
from os import getenv
from .types import File

__all__ = [
    "parameterize",
    "conditional_dispatch",
    "unique_generator",
    "check_if_string_set",
    "convert",
    "serialize_function",
    "pretty_xml",
    "write_xml",
    "get_full_windows_user"
]

"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Parameterized Decorators
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


def parameterize(decorator: Callable) -> Callable:
    """
    Function for parameterizing decorators

    :param decorator: A decorator to parameterize

    :returns: A decorator that can be parameterized
    """

    def outer(*args, **kwargs) -> Callable:
        """
        Outer function that takes arguments and keyword arguments for the decorator

        :param args: Positional arguments for the decorator

        :param kwargs: Keyword arguments for the decorator

        :returns: A function that applies the decorator to the target function
        """

        def inner(func: Callable) -> Callable:
            """
            Inner function that applies the decorator to the target function

            :param func: The target function to be decorated

            :returns: The decorated function
            """
            # noinspection PyArgumentList
            return decorator(func, *args, **kwargs)

        return inner

    return outer


@parameterize
def convert(function: Callable,
            parameter: str,
            permitted: tuple,
            required: Any,
            converter: Optional[Callable] = None,
            ) -> Callable:

    @wraps(function)
    def decorator(*args, **kwargs) -> Callable:
        sig = inspect.signature(function)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        param = bound_args.arguments.get(parameter)
        if isinstance(param, permitted):
            bound_args.arguments = {**bound_args.kwargs, **bound_args.arguments}
            bound_args.arguments.pop("kwargs", None)
            bound_args.arguments[parameter] = converter(param) if converter else required(param)
        else:
            raise TypeError(f"{parameter} must be of type {permitted}")
        return function(**bound_args.arguments)

    return decorator


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Conditional Dispatcher
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


def _find_implementation(registry: dict, *args: Any, **kwargs: Any) -> Callable:
    for condition, function in reversed(registry.items()):
        with suppress(TypeError):
            if condition(*args, **kwargs):
                return function


# noinspection PyUnusedLocal
def _always_true(*args: Any, **kwargs: Any) -> bool:
    return True


def conditional_dispatch(func: Callable) -> Callable:
    """
    Conditional-dispatch generic function decorator that transforms a function into a generic function whose behavior is
    defined by registered (arbitrary) conditional statements. This is useful for breaking up a single function into
    multiple implementations based on different conditions, without having to write a bunch of if-elif-else statements.
    I hate those. You can also use it to implement a multiple-argument type dispatcher, which is pretty cool.
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
// XML Tools
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


def pretty_xml(root: Element) -> str:
    """
    Pretty print an XML element

    :param root: XML element

    :return: pretty printed XML
    """
    xml_string = parseString(tostring(root)).toprettyxml(indent=" " * 2)
    xml_string = xml_string.replace('<?xml version="1.0" ?>',
                                    "<?xml version='1.0' encoding='UTF-16'?>")
    return xml_string


def write_xml(file: File, root: Element) -> None:
    """
    Write an XML element to a file

    :param file: File path

    :param root: XML element
    """
    with open(file, "w", encoding="UTF-16") as file:
        file.write(pretty_xml(root))


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
    everything. Honestly, I don't even remember why I wrote this function. I think I was just bored.
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
    return {iterable, } if isinstance(iterable, str) else set(iterable) \
        if iterable else set()


def serialize_function(call: Callable) -> dict:
    """
    Serialize a function

    :param call: function

    :return: serialized function
    """
    return {
        "name": call.__name__,
        "file": getsourcefile(call)
    }


def get_full_windows_user() -> str:
    """
    Get the full user

    :return: full user
    """
    return getenv('userdomain') + "\\" + getenv('username')