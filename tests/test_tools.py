from pathlib import Path
from unittest.mock import MagicMock

import pytest

# noinspection PyProtectedMember
from exporgo._tools import (check_if_string_set, conditional_dispatch, convert,
                            serialize_function, unique_generator)


def test_convert():
    # generate_decorated function
    # noinspection PyUnusedLocal
    @convert(parameter="a", permitted=(str, Path), required=Path)
    def valid_handle(a, b):
        return 0

    # test valid
    valid_handle("C:\\sqornshellous.zem", None)

    # test invalid
    with pytest.raises(TypeError):
        valid_handle(0, None)

class TestUniqueGenerator:

    def test_unique_elements(self):
        iterable = [1, 2, 2, 3, 4, 4, 5]
        result = list(unique_generator(iterable))
        assert result == [1, 2, 3, 4, 5]

    def test_empty_iterable(self):
        iterable = []
        result = list(unique_generator(iterable))
        assert result == []

    def test_single_element(self):
        iterable = [42]
        result = list(unique_generator(iterable))
        assert result == [42]

    def test_all_duplicates(self):
        iterable = [7, 7, 7, 7]
        result = list(unique_generator(iterable))
        assert result == [7]

    def test_mixed_types(self):
        iterable = [1, 'a', 1, 'b', 'a']
        result = list(unique_generator(iterable))
        assert result == [1, 'a', 'b']

class TestCheckIfStringSet:

    def test_string_input(self):
        result = check_if_string_set("hello")
        assert result == {"hello"}

    def test_list_of_strings(self):
        result = check_if_string_set(["hello", "world"])
        assert result == {"hello", "world"}

    def test_empty_string(self):
        result = check_if_string_set("")
        assert result == {""}

    def test_mixed_iterable(self):
        result = check_if_string_set([1, "hello", 2, "world"])
        assert result == {1, "hello", 2, "world"}

    def test_empty_iterable(self):
        result = check_if_string_set([])
        assert result == set()


# noinspection PyUnresolvedReferences,PyUnusedLocal
class TestConditionalDispatch:

    def test_dispatches_to_correct_function(self):
        @conditional_dispatch
        def func(x):
            return "default"

        @func.register(lambda x: x > 0)
        def positive(x):
            return "positive"

        @func.register(lambda x: x < 0)
        def negative(x):
            return "negative"

        assert func(1) == "positive"
        assert func(-1) == "negative"
        assert func(0) == "default"

    def test_raises_type_error_without_positional_argument(self):
        @conditional_dispatch
        def func(x):
            return "default"

        with pytest.raises(TypeError):
            func()

    def test_handles_multiple_conditions(self):
        @conditional_dispatch
        def func(x, y):
            return "default"

        @func.register(lambda x, y: x > y)
        def greater(x, y):
            return "greater"

        @func.register(lambda x, y: x < y)
        def lesser(x, y):
            return "lesser"

        assert func(3, 2) == "greater"
        assert func(2, 3) == "lesser"
        assert func(2, 2) == "default"

    def test_default_function_called_when_no_conditions_met(self):
        @conditional_dispatch
        def func(x):
            return "default"

        assert func(0) == "default"
        assert func(100) == "default"


def test_function_name_and_file():
    result = serialize_function(check_if_string_set)
    assert result["name"] == "check_if_string_set"
    assert "_tools.py" in result["file"]
