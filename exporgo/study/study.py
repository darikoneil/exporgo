"""The Study container: identities, resources, validation, and persistence.

A :class:`Study` ties together an identity coordinate system, the identities it should
contain, and the resources (files/folders) expected for each. It describes and
validates; it never executes. Identity keys become the datastore's partition keys, and
:meth:`Study.validate` seeds the monitoring layer's derived status.

Saving a study also wires up logging into its directory (see :meth:`Study.init_logging`),
so every study automatically gets a ``<root>/<name>.log`` the logger writes to.
"""

import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import tomli_w

from exporgo.log import LogLevel, init_logger
from exporgo.study.identity import (
    Identity,
    IdentityKey,
    IdentitySchema,
    IdentityValue,
)
from exporgo.study.resources import Resource

if TYPE_CHECKING:
    from exporgo.datastore.spec import StoreSpec
    from exporgo.datastore.store import Store

__all__ = ["Study", "ValidationReport"]

_CONFIG_NAME = "study.toml"


@dataclass(frozen=True)
class ValidationReport:
    """Outcome of :meth:`Study.validate` — which (identity, resource) pairs exist."""

    present: tuple[tuple[Identity, str], ...]
    missing: tuple[tuple[Identity, str], ...]

    @property
    def is_complete(self) -> bool:
        """True when every registered identity has every declared resource on disk."""
        return not self.missing


class Study:
    """A study: an identity coordinate system, registered identities, and resources."""

    def __init__(
        self,
        name: str,
        root: str | Path,
        identity: Iterable[str | IdentityKey] | IdentitySchema | None = None,
    ) -> None:
        """Create a study.

        Args:
            name: A human-readable study name.
            root: The study's root directory on disk.
            identity: The identity keys (1-3), an :class:`IdentitySchema`, or ``None``
                to default to ``["Subject"]``.
        """
        self.name = name
        self.root = Path(root)
        self.identity = self._coerce_schema(identity)
        self._entities: list[Identity] = []
        self._resources: dict[str, Resource] = {}
        self._stores: dict[str, StoreSpec] = {}

    @staticmethod
    def _coerce_schema(
        identity: Iterable[str | IdentityKey] | IdentitySchema | None,
    ) -> IdentitySchema:
        """Normalize the ``identity`` argument into an :class:`IdentitySchema`."""
        if identity is None:
            return IdentitySchema.default()
        if isinstance(identity, IdentitySchema):
            return identity
        keys = tuple(
            IdentityKey(name=key) if isinstance(key, str) else key for key in identity
        )
        return IdentitySchema(keys=keys)

    @property
    def entities(self) -> tuple[Identity, ...]:
        """The registered identities, in registration order."""
        return tuple(self._entities)

    @property
    def resources(self) -> dict[str, Resource]:
        """The declared resources, keyed by name."""
        return dict(self._resources)

    def register(self, **values: IdentityValue) -> Identity:
        """Register an identity the study should contain (a declared expectation)."""
        identity = self.identity.identity(**values)
        if identity not in self._entities:
            self._entities.append(identity)
        return identity

    def declare_resource(self, name: str, template: str) -> Resource:
        """Declare a named resource located by a path template over the identity keys.

        Raises:
            ValueError: If the template references keys not in the study's identity.
        """
        resource = Resource(name=name, template=template)
        unknown = [
            key for key in resource.placeholders if key not in self.identity.names
        ]
        if unknown:
            msg = (
                f"Resource {name!r} template uses unknown identity keys {unknown}; "
                f"study identity keys are {list(self.identity.names)}."
            )
            raise ValueError(msg)
        self._resources[name] = resource
        return resource

    def path(self, resource: str, **values: IdentityValue) -> Path:
        """Resolve the on-disk path of ``resource`` for the given identity values.

        Raises:
            KeyError: If no resource with that name has been declared.
        """
        identity = self.identity.identity(**values)
        try:
            spec = self._resources[resource]
        except KeyError:
            msg = (
                f"No resource named {resource!r}; "
                f"declared resources: {sorted(self._resources)}"
            )
            raise KeyError(msg) from None
        return spec.resolve(self.root, identity)

    def declare_store(
        self,
        name: str,
        columns: Mapping[str, Any],
        *,
        partition_keys: Sequence[str] | None = None,
        sort_column: str | None = None,
    ) -> "StoreSpec":
        """Declare a datastore component; partition keys default to the identity keys.

        Args:
            name: The store's name (also its subdirectory under the study root).
            columns: The store's ``column -> polars dtype`` schema (must include the
                partition keys); any polars dtype, at full fidelity.
            partition_keys: Columns to partition by (1-3); defaults to the study's
                identity keys.
            sort_column: Optional column to sort by within partitions.

        Returns:
            The created :class:`~exporgo.datastore.spec.StoreSpec`.
        """
        from exporgo.datastore.spec import StoreSpec

        keys = (
            tuple(partition_keys) if partition_keys is not None else self.identity.names
        )
        spec = StoreSpec(
            name=name,
            columns=dict(columns),
            partition_keys=keys,
            sort_column=sort_column,
        )
        self._stores[name] = spec
        return spec

    def store(self, name: str) -> "Store":
        """Return the :class:`~exporgo.datastore.store.Store` for a declared component.

        Raises:
            KeyError: If no store with that name has been declared.
        """
        from exporgo.datastore.store import Store

        try:
            spec = self._stores[name]
        except KeyError:
            msg = f"No store named {name!r}; declared stores: {sorted(self._stores)}"
            raise KeyError(msg) from None
        return Store(self.root / name, spec)

    def validate(self) -> ValidationReport:
        """Check each registered identity against each declared resource on disk."""
        present: list[tuple[Identity, str]] = []
        missing: list[tuple[Identity, str]] = []
        for identity in self._entities:
            for name, resource in self._resources.items():
                target = resource.resolve(self.root, identity)
                bucket = present if target.exists() else missing
                bucket.append((identity, name))
        return ValidationReport(present=tuple(present), missing=tuple(missing))

    def init_logging(
        self,
        *,
        name: str | None = None,
        log_level_console: LogLevel = LogLevel.INFO,
        log_level_custom: LogLevel | None = None,
    ) -> None:
        """Configure logging to write into this study's directory.

        Materializes the study root if needed and drives
        :func:`exporgo.log.init_logger` with ``base_directory`` set to the study root and
        ``file_stem`` set to the study name, so a study automatically has its own log
        file. Called automatically by :meth:`save`; call it directly to start logging into
        the study before the first save (e.g. when resuming a study via :meth:`load`).

        Writes ``<root>/<name>.log`` (INFO/WARNING) and
        ``<root>/.logs/.<name>_exception.log`` (exceptions), and adds a colorized console
        sink. Like :func:`~exporgo.log.init_logger` it resets existing sinks, so repeated
        calls are safe and idempotent.

        Args:
            name: Loguru namespace to enable; ``None`` (the default) enables all
                namespaces, so the study log captures both exporgo's own records and your
                analysis code.
            log_level_console: Minimum level shown on the console.
            log_level_custom: If given, adds a file sink capturing records at or above
                this threshold (see :func:`~exporgo.log.init_logger`).
        """
        self.root.mkdir(parents=True, exist_ok=True)
        init_logger(
            name=name,
            base_directory=self.root,
            log_level_console=log_level_console,
            log_level_custom=log_level_custom,
            file_stem=self.name,
        )

    def save(self) -> Path:
        """Write the study's declaration to ``root/study.toml`` and return that path.

        Also initializes logging into the study root (see :meth:`init_logging`), so a
        saved study automatically has a ``<root>/<name>.log`` the logger writes to.
        """
        data: dict[str, object] = {
            "name": self.name,
            "identity": [
                {"name": key.name, "dtype": key.dtype} for key in self.identity.keys
            ],
            "resources": {
                name: resource.template for name, resource in self._resources.items()
            },
            "entities": [identity.to_dict() for identity in self._entities],
        }
        stores: dict[str, dict[str, object]] = {}
        for store_name, spec in self._stores.items():
            entry: dict[str, object] = {"partition_keys": list(spec.partition_keys)}
            if spec.sort_column is not None:
                entry["sort_column"] = spec.sort_column
            stores[store_name] = entry
        data["stores"] = stores
        self.root.mkdir(parents=True, exist_ok=True)
        config_path = self.root / _CONFIG_NAME
        with config_path.open("wb") as handle:
            tomli_w.dump(data, handle)
        for store_name in self._stores:
            self.store(store_name).write_schema()  # persist each store's schema anchor
        self.init_logging()
        return config_path

    @classmethod
    def load(cls, root: str | Path) -> Self:
        """Reconstruct a study from ``root/study.toml`` (the declaration only)."""
        root = Path(root)
        with (root / _CONFIG_NAME).open("rb") as handle:
            data = tomllib.load(handle)
        keys = [IdentityKey.model_validate(spec) for spec in data["identity"]]
        study = cls(name=data["name"], root=root, identity=keys)
        for name, template in data.get("resources", {}).items():
            study.declare_resource(name, template)
        stores_data = data.get("stores", {})
        if stores_data:
            from exporgo.datastore.store import Store

            for store_name, entry in stores_data.items():
                study.declare_store(
                    store_name,
                    Store.read_schema(root / store_name),
                    partition_keys=entry["partition_keys"],
                    sort_column=entry.get("sort_column"),
                )
        for entity in data.get("entities", []):
            study.register(**entity)
        return study
