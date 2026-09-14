"""Tests for the identity model: IdentityKey, IdentitySchema, Identity."""

import pytest
from pydantic import ValidationError

from exporgo.experiment.identity import Identity, IdentityKey, IdentitySchema


# ---------------------------------------------------------------------- IdentityKey
def test_identity_key_defaults_to_string_dtype() -> None:
    key = IdentityKey(name="Subject")
    assert key.name == "Subject"
    assert key.dtype == "str"


def test_identity_key_coerces_values_to_declared_dtype() -> None:
    assert IdentityKey(name="Session", dtype="int").coerce("3") == 3
    assert IdentityKey(name="Subject").coerce(42) == "42"


# ------------------------------------------------------------------- IdentitySchema
def test_schema_default_is_single_subject_key() -> None:
    schema = IdentitySchema.default()
    assert schema.names == ("Subject",)
    assert len(schema) == 1


def test_schema_normalizes_string_and_key_specs() -> None:
    schema = IdentitySchema(keys=["Subject", IdentityKey(name="Session", dtype="int")])
    assert schema.names == ("Subject", "Session")


def test_schema_rejects_more_than_three_keys() -> None:
    with pytest.raises(ValidationError):
        IdentitySchema(keys=["a", "b", "c", "d"])


def test_schema_rejects_no_keys() -> None:
    with pytest.raises(ValidationError):
        IdentitySchema(keys=[])


def test_schema_rejects_duplicate_key_names() -> None:
    with pytest.raises(ValidationError):
        IdentitySchema(keys=["Subject", "Subject"])


# ------------------------------------------------------------- Identity (via schema)
def test_identity_validates_and_coerces_values() -> None:
    schema = IdentitySchema(keys=["Subject", IdentityKey(name="Session", dtype="int")])

    ident = schema.identity(Subject="m01", Session="3")  # "3" coerced to int

    assert ident["Subject"] == "m01"
    assert ident["Session"] == 3


def test_identity_requires_exactly_the_schema_keys() -> None:
    schema = IdentitySchema(keys=["Subject", "Session"])

    with pytest.raises(ValueError, match="Session"):
        schema.identity(Subject="m01")  # missing Session
    with pytest.raises(ValueError, match="Extra"):
        schema.identity(Subject="m01", Session=1, Extra=9)  # unexpected key


def test_identity_as_path_is_hive_style_in_key_order() -> None:
    schema = IdentitySchema(keys=["Subject", IdentityKey(name="Session", dtype="int")])

    ident = schema.identity(Subject="m01", Session=1)

    assert ident.as_path() == "Subject=m01/Session=1"


def test_identity_is_hashable_and_equal_by_value() -> None:
    schema = IdentitySchema(keys=["Subject"])

    first = schema.identity(Subject="m01")
    second = schema.identity(Subject="m01")
    other = schema.identity(Subject="m02")

    assert first == second
    assert hash(first) == hash(second)
    assert first != other
    assert len({first, second, other}) == 2


def test_bool_key_parses_textual_false_as_false() -> None:
    key = IdentityKey(name="Flag", dtype="bool")

    assert key.coerce("False") is False
    assert key.coerce("false") is False
    assert key.coerce("0") is False


def test_bool_key_parses_textual_true_as_true() -> None:
    key = IdentityKey(name="Flag", dtype="bool")

    assert key.coerce("True") is True
    assert key.coerce("true") is True
    assert key.coerce("1") is True


def test_bool_key_passes_actual_bools_through() -> None:
    key = IdentityKey(name="Flag", dtype="bool")

    assert key.coerce(True) is True
    assert key.coerce(False) is False


def test_bool_key_accepts_zero_and_one_ints() -> None:
    key = IdentityKey(name="Flag", dtype="bool")

    assert key.coerce(1) is True
    assert key.coerce(0) is False


def test_bool_key_rejects_unrecognized_text() -> None:
    key = IdentityKey(name="Flag", dtype="bool")

    with pytest.raises(ValueError, match="bool"):
        key.coerce("banana")


def test_bool_identity_round_trips_false_through_schema() -> None:
    schema = IdentitySchema(keys=[IdentityKey(name="Flag", dtype="bool")])

    identity = schema.identity(Flag="False")

    assert identity["Flag"] is False
