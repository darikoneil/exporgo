"""Tests for the identity model: IdentityKey, IdentitySchema, Identity."""

import pytest
from pydantic import ValidationError

from exporgo.study.identity import Identity, IdentityKey, IdentitySchema


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
