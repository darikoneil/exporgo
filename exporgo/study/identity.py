"""A study's coordinate system and its concrete addresses.

A study is organized along a small set of named axes — its :class:`IdentitySchema`,
an ordered 1-3 :class:`IdentityKey`s (default ``["Subject"]``). A concrete point in
that system is an :class:`Identity` (e.g. ``Subject="m01", Session=1``), which the
datastore uses as its partition path and the monitoring layer tracks.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

__all__ = ["Identity", "IdentityKey", "IdentitySchema"]

_MIN_KEYS = 1
_MAX_KEYS = 3

type IdentityValue = str | int | float | bool
"""The value types an identity key may take."""

type DType = Literal["str", "int", "float", "bool"]
"""Allowed identity-key dtype labels (strings, so they round-trip through config)."""

_COERCERS: dict[str, Callable[..., IdentityValue]] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
}
"""Maps each dtype label to the callable that coerces a value to it."""


class IdentityKey(BaseModel):
    """A named, typed axis of a study's identity (e.g. ``Subject``, ``Session``).

    Attributes:
        name: The axis name, used as the keyword when addressing an identity and as the
            Hive partition key on disk.
        dtype: The value type — one of ``"str"``, ``"int"``, ``"float"``, ``"bool"``;
            stored as a string label so it round-trips through ``study.toml``.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: str
    dtype: DType = "str"

    def coerce(self, value: IdentityValue) -> IdentityValue:
        """Coerce a value to this key's declared dtype.

        Args:
            value: The value to coerce (e.g. the string ``"1"`` for an ``int`` key).

        Returns:
            The value converted by the dtype's callable
            (``str`` / ``int`` / ``float`` / ``bool``).

        Raises:
            ValueError: If the value cannot be converted to the declared dtype (e.g.
                ``int("m01")``).
        """
        return _COERCERS[self.dtype](value)


class IdentitySchema(BaseModel):
    """An ordered set of 1-3 identity keys — a study's coordinate system."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    keys: tuple[IdentityKey, ...]

    @field_validator("keys", mode="before")
    @classmethod
    def _normalize_keys(cls, value: object) -> object:
        """Accept plain strings or dicts as key specs, not just IdentityKeys."""
        if not isinstance(value, (list, tuple)):
            return value
        normalized: list[object] = []
        for item in value:
            if isinstance(item, str):
                normalized.append(IdentityKey(name=item))
            elif isinstance(item, dict):
                normalized.append(IdentityKey(**item))
            else:
                normalized.append(item)
        return normalized

    @model_validator(mode="after")
    def _validate_bounds_and_uniqueness(self) -> Self:
        """Enforce the 1-3 key bound and unique key names."""
        count = len(self.keys)
        if not _MIN_KEYS <= count <= _MAX_KEYS:
            msg = f"A study needs {_MIN_KEYS}-{_MAX_KEYS} identity keys, got {count}."
            raise ValueError(msg)
        names = [key.name for key in self.keys]
        if len(set(names)) != len(names):
            msg = f"Identity key names must be unique, got {names}."
            raise ValueError(msg)
        return self

    @classmethod
    def default(cls) -> Self:
        """Return the default single-key schema (``["Subject"]``)."""
        return cls(keys=(IdentityKey(name="Subject"),))

    @property
    def names(self) -> tuple[str, ...]:
        """The ordered identity key names."""
        return tuple(key.name for key in self.keys)

    def __len__(self) -> int:
        """The number of identity keys."""
        return len(self.keys)

    def identity(self, **values: IdentityValue) -> "Identity":
        """Build a validated :class:`Identity` over this schema.

        Requires exactly the schema's keys, coercing each value to its key's dtype.

        Args:
            **values: One value per identity key, keyed by key name.

        Returns:
            The validated :class:`Identity`.

        Raises:
            ValueError: If a key is missing or an unexpected key is supplied.
        """
        provided = set(values)
        expected = set(self.names)
        missing = expected - provided
        if missing:
            msg = f"Missing identity keys: {sorted(missing)}"
            raise ValueError(msg)
        extra = provided - expected
        if extra:
            msg = f"Extra/unexpected identity keys: {sorted(extra)}"
            raise ValueError(msg)
        coerced = tuple(key.coerce(values[key.name]) for key in self.keys)
        return Identity(keys=self.names, values=coerced)


@dataclass(frozen=True, slots=True)
class Identity:
    """One concrete address in a study's identity coordinate system.

    Immutable and hashable, so an identity can index dictionaries and sets. Its
    :meth:`as_path` rendering *is* the datastore partition path, so the identity you
    register, query, and attach data to lines up across the study and datastore layers.

    Attributes:
        keys: The identity key names, in schema order.
        values: The coerced value for each key, positionally aligned with ``keys``.
    """

    keys: tuple[str, ...]
    values: tuple[IdentityValue, ...]

    def __getitem__(self, key: str) -> IdentityValue:
        """Return the value for one identity key."""
        return self.values[self.keys.index(key)]

    def as_path(self) -> str:
        """Render as a Hive-style partition path fragment (``key=value/…``).

        This is exactly the sub-path the datastore partitions on, so resource paths and
        store partitions for the same identity line up on disk.

        Returns:
            The path fragment, e.g. ``"Subject=m01/Session=1"``.
        """
        return "/".join(
            f"{key}={value}" for key, value in zip(self.keys, self.values, strict=True)
        )

    def to_dict(self) -> dict[str, IdentityValue]:
        """Return the identity as an ordered ``{key: value}`` mapping."""
        return dict(zip(self.keys, self.values, strict=True))

    def __repr__(self) -> str:
        """Return e.g. ``Identity(Subject='m01', Session=1)``."""
        inner = ", ".join(
            f"{key}={value!r}"
            for key, value in zip(self.keys, self.values, strict=True)
        )
        return f"Identity({inner})"
