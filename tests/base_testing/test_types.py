import pytest

# noinspection PyProtectedMember
from exporgo.types import EnumNameValueMismatchError, _ExporgoIntEnum


class TestExporgoIntEnum:

    def test_deserializes_valid_string(self):
        class TestEnum(_ExporgoIntEnum):
            TEST = 1

        result = TestEnum.__deserialize__("(TEST, 1)")
        assert result == TestEnum.TEST

    def test_deserializes_valid_tuple(self):
        class TestEnum(_ExporgoIntEnum):
            TEST = 1

        # noinspection PyTypeChecker
        result = TestEnum.__deserialize__(("TEST", 1))
        assert result == TestEnum.TEST

    def test_raises_type_error_for_invalid_type(self):
        class TestEnum(_ExporgoIntEnum):
            TEST = 1

        with pytest.raises(TypeError):
            # noinspection PyTypeChecker
            TestEnum.__deserialize__(123)

    def test_raises_enum_name_value_mismatch_error(self):
        class TestEnum(_ExporgoIntEnum):
            TEST = 1

        with pytest.raises(EnumNameValueMismatchError):
            TestEnum.__deserialize__("(WRONG, 1)")

    def test_serializes_enum(self):
        class TestEnum(_ExporgoIntEnum):
            TEST = 1

        result = TestEnum.TEST.__serialize__()
        assert result == "(TEST, 1)"
