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
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import tomli_w
from loguru import logger

from exporgo.log import LogLevel, init_logger
from exporgo.study.filemaps import FileMap
from exporgo.study.identity import (
    Identity,
    IdentityKey,
    IdentitySchema,
    IdentityValue,
)
from exporgo.study.resources import Resource, ResourceSpec

if TYPE_CHECKING:
    from exporgo.datastore.spec import StoreSpec
    from exporgo.datastore.store import Store

__all__ = ["CoverageReport", "Study", "ValidationReport"]

_CONFIG_NAME = "study.toml"


def _rows_to_toml(value: int | None) -> int:
    """Encode a ``max_rows`` setting for ``study.toml`` (``None`` -> the 0 sentinel)."""
    return 0 if value is None else value


def _rows_from_toml(value: int | None, default: int | None) -> int | None:
    """Decode a persisted ``max_rows`` value (absent -> default, 0 sentinel -> ``None``)."""
    if value is None:
        return default
    return None if value == 0 else value


@dataclass(frozen=True)
class ValidationReport:
    """Outcome of :meth:`Study.validate` — which (identity, resource) pairs exist.

    The filesystem is the source of truth: each registered identity is paired with each
    declared resource and bucketed by whether that resource exists on disk. The report
    is a plain snapshot holding no live handles, so it is safe to store or diff across
    runs (e.g. to seed the monitoring layer's derived status).

    Attributes:
        present: ``(identity, resource_name)`` pairs whose resolved path exists.
        missing: ``(identity, resource_name)`` pairs whose resolved path is absent.
    """

    present: tuple[tuple[Identity, str], ...]
    missing: tuple[tuple[Identity, str], ...]

    @property
    def is_complete(self) -> bool:
        """True when every registered identity has every declared resource on disk."""
        return not self.missing


@dataclass(frozen=True)
class CoverageReport:
    """Which identities each component (store/resource) contains, derived on demand.

    Generalizes :class:`ValidationReport` across both stores and resources. Resources are
    reported closed-world (registered identities whose file exists); stores are reported
    open-world from their manifest, so a store may contain identities that were never
    registered -- those land in ``unregistered`` (drift) rather than ``missing``.

    Attributes:
        present: ``(identity, component_name)`` pairs where the registered identity is
            contained in that store/resource.
        missing: ``(identity, component_name)`` pairs where a registered identity is
            absent from that component.
        unregistered: ``(identity, store_name)`` pairs for identities physically present
            in a store but not registered in the study (store-only drift).
    """

    present: tuple[tuple[Identity, str], ...]
    missing: tuple[tuple[Identity, str], ...]
    unregistered: tuple[tuple[Identity, str], ...]

    @property
    def is_complete(self) -> bool:
        """True when every registered identity is present in every declared component."""
        return not self.missing

    def identities(self, component: str) -> set[Identity]:
        """The identities present in the named store or resource."""
        return {identity for identity, name in self.present if name == component}

    def components(self, identity: Identity) -> set[str]:
        """The store/resource names that contain the given identity."""
        return {name for present, name in self.present if present == identity}


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
        self._resources: dict[str, ResourceSpec] = {}
        self._stores: dict[str, StoreSpec] = {}
        self._filemaps: list[str] = []

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

    def __repr__(self) -> str:
        """Return an unambiguous representation of the study for debugging."""
        return (
            f"{type(self).__name__}(name={self.name!r}, root={self.root!r}, "
            f"identity={self.identity.names!r})"
        )

    def __str__(self) -> str:
        """Return a concise one-line human-readable summary of the study."""
        keys = ", ".join(self.identity.names)
        return (
            f"Study {self.name!r} [{keys}]: {len(self._entities)} identities, "
            f"{len(self._resources)} resources, {len(self._stores)} stores, "
            f"{len(self._filemaps)} filemaps"
        )

    def print(self) -> None:
        """Print a multi-line summary of the study's declared contents to stdout.

        Reports the study name and root, its identity keys, and the counts (and names)
        of registered identities, declared resources, stores, and filemaps.
        """
        resources = ", ".join(sorted(self._resources)) or "(none)"
        stores = ", ".join(sorted(self._stores)) or "(none)"
        filemaps = ", ".join(sorted(self._filemaps)) or "(none)"
        keys = ", ".join(self.identity.names)
        lines = [
            f"Study {self.name!r}",
            f"  root:       {self.root}",
            f"  identity:   {keys}",
            f"  identities: {len(self._entities)} registered",
            f"  resources:  {len(self._resources)} ({resources})",
            f"  stores:     {len(self._stores)} ({stores})",
            f"  filemaps:   {len(self._filemaps)} ({filemaps})",
        ]
        print("\n".join(lines))

    @property
    def entities(self) -> tuple[Identity, ...]:
        """The registered identities, as an immutable snapshot in registration order."""
        return tuple(self._entities)

    @property
    def resources(self) -> dict[str, ResourceSpec]:
        """The declared resource specs, keyed by name (a copy; safe to mutate)."""
        return dict(self._resources)

    @property
    def stores(self) -> dict[str, "StoreSpec"]:
        """The declared store specs, keyed by name (a copy; safe to mutate)."""
        return dict(self._stores)

    @property
    def filemaps(self) -> dict[str, FileMap]:
        """The declared filemaps, keyed by name.

        Returns the :class:`~exporgo.study.filemaps.FileMap` handles (a filemap has no
        separate spec, so this returns the components themselves rather than declarations).
        """
        return {name: self.filemap(name) for name in self._filemaps}

    def register(self, **values: IdentityValue) -> Identity:
        """Register an identity the study should contain (a declared expectation).

        Registration records what *should* exist; it never touches the filesystem. This
        declared expectation is what lets :meth:`validate` detect missing data.
        Re-registering an identical identity is a no-op (identities are de-duplicated).

        Args:
            **values: One value per identity key, keyed by key name (e.g.
                ``Subject="m01", Session=1``); each is coerced to its key's dtype.

        Returns:
            The registered :class:`~exporgo.study.identity.Identity`.

        Raises:
            ValueError: If a key is missing or an unexpected key is supplied.
        """
        identity = self.identity.identity(**values)
        if identity not in self._entities:
            self._entities.append(identity)

        msg = f"Registered {values} to {self.name}"
        logger.info(msg)

        return identity

    def declare_resource(self, name: str, template: str) -> ResourceSpec:
        """Declare a named resource located by a path template over the identity keys.

        A resource is a file/folder the study expects at each identity (e.g. ``"raw"``,
        ``"suite2p"``). Its ``template`` uses ``{KeyName}`` placeholders drawn from any
        subset of the study's identity keys and is resolved against the study root by
        :meth:`path` / :meth:`resource` and :meth:`validate`.

        Args:
            name: The resource's name (its handle in :meth:`resource` / :meth:`path`).
            template: A path template over the identity keys, e.g.
                ``"{Subject}/{Session}/behavior.csv"``.

        Returns:
            The declared :class:`~exporgo.study.resources.ResourceSpec`.

        Raises:
            ValueError: If the template references keys not in the study's identity.
        """
        spec = ResourceSpec(name=name, template=template)
        unknown = [key for key in spec.placeholders if key not in self.identity.names]
        if unknown:
            msg = (
                f"Resource {name!r} template uses unknown identity keys {unknown}; "
                f"study identity keys are {list(self.identity.names)}."
            )
            raise ValueError(msg)
        self._resources[name] = spec

        msg = f"Declared the resource {spec}"
        logger.info(msg)

        return spec

    def resource(self, name: str) -> Resource:
        """Return the root-bound :class:`~exporgo.study.resources.Resource` handle.

        Binds the named resource's declaration to the study root and identity schema, so
        you can resolve paths (:meth:`Resource.path`) and check existence
        (:meth:`Resource.exists`) for specific identity values. This is the resource
        counterpart of :meth:`store`.

        Args:
            name: The name of a previously declared resource.

        Returns:
            The :class:`~exporgo.study.resources.Resource` bound to this study's root.

        Raises:
            KeyError: If no resource with that name has been declared.
        """
        try:
            spec = self._resources[name]
        except KeyError:
            msg = (
                f"No resource named {name!r}; "
                f"declared resources: {sorted(self._resources)}"
            )
            raise KeyError(msg) from None
        return Resource(self.root, spec, self.identity)

    def path(self, resource: str, **values: IdentityValue) -> Path:
        """Resolve the on-disk path of ``resource`` for the given identity values.

        Shorthand for ``self.resource(resource).path(**values)`` — the terse one-shot for
        when you just need the location. The path is returned whether or not it exists;
        use :meth:`validate` to check existence.

        Args:
            resource: The name of a previously declared resource.
            **values: One value per identity key, keyed by key name.

        Returns:
            The resolved path under the study root.

        Raises:
            KeyError: If no resource with that name has been declared.
            ValueError: If a key is missing or an unexpected key is supplied.
        """
        return self.resource(resource).path(**values)

    def declare_store(
        self,
        name: str,
        columns: Mapping[str, Any],
        *,
        partition_keys: Sequence[str] | None = None,
        sort_column: str | None = None,
        max_rows_per_file: int | None = 25_000_000,
        max_rows_per_group: int | None = None,
    ) -> "StoreSpec":
        """Declare a datastore component; partition keys default to the identity keys.

        Args:
            name: The store's name (also its subdirectory under the study root).
            columns: The store's ``column -> polars dtype`` schema (must include the
                partition keys); any polars dtype, at full fidelity.
            partition_keys: Columns to partition by (1-3); defaults to the study's
                identity keys.
            sort_column: Optional column to sort by within partitions.
            max_rows_per_file: Write-time cap on rows per Parquet fragment (``None`` = no
                exporgo-imposed limit). Part of the declaration, so it survives save/load.
            max_rows_per_group: Write-time cap on rows per row group (``None`` = pyarrow's
                default). Part of the declaration, so it survives save/load.

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
            max_rows_per_file=max_rows_per_file,
            max_rows_per_group=max_rows_per_group,
        )
        self._stores[name] = spec

        msg = f"Declared the store {spec}"
        logger.info(msg)

        return spec

    def store(self, name: str) -> "Store":
        """Return the :class:`~exporgo.datastore.store.Store` for a declared component.

        Binds the store's declared spec to ``<root>/<name>`` so it can be written to and
        scanned. The return type lives in the datastore extra, so it is imported lazily;
        ``import exporgo.study`` alone does not pull in the datastore layer.

        Args:
            name: The name of a previously declared store.

        Returns:
            The :class:`~exporgo.datastore.store.Store` bound to ``<root>/<name>``.

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

    def declare_filemap(self, name: str) -> FileMap:
        """Declare a filemap component and return its handle.

        A filemap records the concrete location(s) of particular files for each identity
        (see :class:`~exporgo.study.filemaps.FileMap`) -- the third component type beside
        resources and stores. It has no declaration beyond its name; the recorded paths
        live in a sidecar ``<root>/<name>/_filemap.json`` written by the handle.

        Args:
            name: The filemap's name (also its subdirectory under the study root).

        Returns:
            The :class:`~exporgo.study.filemaps.FileMap` handle bound to ``<root>/<name>``.
        """
        if name not in self._filemaps:
            self._filemaps.append(name)

        msg = f"Declared the filemap {name!r}"
        logger.info(msg)

        return self.filemap(name)

    def filemap(self, name: str) -> FileMap:
        """Return the :class:`~exporgo.study.filemaps.FileMap` handle for a component.

        Args:
            name: The name of a previously declared filemap.

        Returns:
            The :class:`~exporgo.study.filemaps.FileMap` bound to ``<root>/<name>``.

        Raises:
            KeyError: If no filemap with that name has been declared.
        """
        if name not in self._filemaps:
            msg = (
                f"No filemap named {name!r}; "
                f"declared filemaps: {sorted(self._filemaps)}"
            )
            raise KeyError(msg)
        return FileMap(self.root / name, name, self.identity)

    def validate(self) -> ValidationReport:
        """Check each registered identity against each declared resource on disk.

        Resolves every ``(registered identity, declared resource)`` pair to a path and
        records whether it exists — the file-existence self-check at the heart of the
        study model. The filesystem is the source of truth; nothing is cached, so the
        report always reflects the tree as it is at call time.

        Returns:
            A :class:`ValidationReport` partitioning the pairs into ``present`` and
            ``missing``.

        Note:
            Cost is ``O(registered identities * declared resources)`` filesystem
            ``stat`` calls, existence-only; file contents are never read.
        """
        present: list[tuple[Identity, str]] = []
        missing: list[tuple[Identity, str]] = []
        for identity in self._entities:
            for name, resource in self._resources.items():
                target = resource.resolve(self.root, identity)
                bucket = present if target.exists() else missing
                bucket.append((identity, name))
        return ValidationReport(present=tuple(present), missing=tuple(missing))

    def identities(
        self,
        *,
        store: str | None = None,
        resource: str | None = None,
        filemap: str | None = None,
    ) -> set[Identity]:
        """Return the identities contained in one declared store, resource, or filemap.

        Exactly one target must be given. A **store** and a **filemap** are reported
        open-world (the store's manifest partitions / the filemap's recorded identities),
        so they may include identities never registered in the study. A **resource** is
        reported closed-world -- the registered identities whose resolved file exists on
        disk (there is no scan for unregistered files; that is :meth:`discover`'s role).

        Args:
            store: The name of a declared store to inventory, or ``None``.
            resource: The name of a declared resource to inventory, or ``None``.
            filemap: The name of a declared filemap to inventory, or ``None``.

        Returns:
            The contained :class:`~exporgo.study.identity.Identity` objects. Store
            identities are built over the store's partition keys; resource identities are
            the registered identities that are present; filemap identities are those with
            at least one recorded file.

        Raises:
            ValueError: If not exactly one target is given.
            KeyError: If no store/resource/filemap with that name has been declared.
        """
        provided = [name for name in (store, resource, filemap) if name is not None]
        if len(provided) != 1:
            msg = "identities() requires exactly one of 'store', 'resource', 'filemap'."
            raise ValueError(msg)
        if store is not None:
            component = self.store(store)
            return {
                self._identity_from_partition(component.spec.partition_keys, partition)
                for partition in component.manifest().partitions()
            }
        if resource is not None:
            handle = self.resource(resource)
            return {
                entity for entity in self._entities if handle.exists(**entity.to_dict())
            }
        assert filemap is not None  # the only remaining option after the guard above
        return self.filemap(filemap).identities()

    def _identity_from_partition(
        self, partition_keys: tuple[str, ...], partition: Mapping[str, str]
    ) -> Identity:
        """Coerce a manifest partition dict into a typed :class:`Identity`."""
        key_by_name = {key.name: key for key in self.identity.keys}
        values = tuple(
            key_by_name[name].coerce(partition[name])
            if name in key_by_name
            else partition[name]
            for name in partition_keys
        )
        return Identity(keys=tuple(partition_keys), values=values)

    def _project(self, identity: Identity, keys: tuple[str, ...]) -> Identity | None:
        """Project a registered identity onto ``keys`` (``None`` if a key isn't in it)."""
        try:
            values = tuple(identity[key] for key in keys)
        except ValueError:
            return None
        return Identity(keys=tuple(keys), values=values)

    def coverage(self) -> CoverageReport:
        """Report which registered identities each declared store/resource contains.

        Generalizes :meth:`validate` to cover resources (existence of the declared file),
        stores (presence in the store's manifest), and filemaps (a recorded location for
        the identity), classifying every ``(registered identity, component)`` pair as
        present or missing. Store/filemap identities present on disk but not registered are
        collected in :attr:`CoverageReport.unregistered` (drift). Filesystem/manifest =
        truth; nothing is cached.

        Returns:
            A :class:`CoverageReport` over registered identities and declared components.
        """
        present: list[tuple[Identity, str]] = []
        missing: list[tuple[Identity, str]] = []
        unregistered: list[tuple[Identity, str]] = []

        for resource_name in self._resources:
            contained = self.identities(resource=resource_name)
            for identity in self._entities:
                bucket = present if identity in contained else missing
                bucket.append((identity, resource_name))

        for store_name, spec in self._stores.items():
            contained = self.identities(store=store_name)
            projected: set[Identity] = set()
            for identity in self._entities:
                projection = self._project(identity, spec.partition_keys)
                if projection is None:
                    continue
                projected.add(projection)
                bucket = present if projection in contained else missing
                bucket.append((identity, store_name))
            unregistered.extend(
                (extra, store_name)
                for extra in sorted(contained - projected, key=Identity.as_path)
            )

        registered = set(self._entities)
        for filemap_name in self._filemaps:
            contained = self.identities(filemap=filemap_name)
            for identity in self._entities:
                bucket = present if identity in contained else missing
                bucket.append((identity, filemap_name))
            unregistered.extend(
                (extra, filemap_name)
                for extra in sorted(contained - registered, key=Identity.as_path)
            )

        return CoverageReport(
            present=tuple(present),
            missing=tuple(missing),
            unregistered=tuple(unregistered),
        )

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
        saved study automatically has a ``<root>/<name>.log`` the logger writes to. The
        **first** save (when ``study.toml`` does not yet exist) records a "created" line
        with the creation date to that log; subsequent saves record a plain "saved" line.
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
            entry: dict[str, object] = {
                "partition_keys": list(spec.partition_keys),
                "max_rows_per_file": _rows_to_toml(spec.max_rows_per_file),
                "max_rows_per_group": _rows_to_toml(spec.max_rows_per_group),
            }
            if spec.sort_column is not None:
                entry["sort_column"] = spec.sort_column
            stores[store_name] = entry
        data["stores"] = stores
        data["filemaps"] = list(self._filemaps)
        self.root.mkdir(parents=True, exist_ok=True)
        config_path = self.root / _CONFIG_NAME
        is_first_save = not config_path.exists()  # before we (over)write it below
        with config_path.open("wb") as handle:
            tomli_w.dump(data, handle)
        for store_name in self._stores:
            self.store(store_name).write_schema()  # persist each store's schema anchor
        self.init_logging()
        if is_first_save:
            creation_date = datetime.now(UTC).isoformat(timespec="seconds")
            msg = (
                f"Study {self.name!r} created {creation_date} (saved to {config_path})."
            )
        else:
            msg = f"Study {self.name!r} saved to {config_path}."
        logger.info(msg)
        return config_path

    @classmethod
    def load(cls, root: str | Path) -> Self:
        """Reconstruct a study from ``root/study.toml`` (the declaration only).

        Restores the declared structure — identity keys, registered identities, resource
        templates, and store specs — but not the data or any derived status, which are
        re-read from the filesystem on demand (filesystem = truth). Loading does *not*
        reconfigure logging (it adds no sinks); it only emits an access log record, which
        is captured if logging is already configured. Call :meth:`init_logging` to resume
        logging into a loaded study.

        Args:
            root: The study root directory containing ``study.toml``.

        Returns:
            The reconstructed :class:`Study`.

        Raises:
            FileNotFoundError: If ``root/study.toml`` does not exist.
        """
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
                    max_rows_per_file=_rows_from_toml(
                        entry.get("max_rows_per_file"), 25_000_000
                    ),
                    max_rows_per_group=_rows_from_toml(
                        entry.get("max_rows_per_group"), None
                    ),
                )
        for filemap_name in data.get("filemaps", []):
            study.declare_filemap(filemap_name)
        for entity in data.get("entities", []):
            study.register(**entity)
        msg = f"Study {study.name!r} accessed (loaded from {root / _CONFIG_NAME})."
        logger.info(msg)
        return study
