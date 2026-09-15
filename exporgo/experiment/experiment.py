"""The Experiment container: identities, resources, validation, and persistence.

An :class:`Experiment` is the **data-side unit**: it lives at the data root (typically on
the lab server) and owns one root, one identity coordinate system, and one store catalog.
A workspace's ``experiments/<name>/`` folder (the Rust CLI side) merely points at that
data root. The experiment ties together the identity coordinate system, the identities it
should contain, and the components (resources, stores, array stores, dumps) expected for
each. It describes and validates; it never executes. Identity keys become the datastore's
partition keys, and :meth:`Experiment.validate` seeds the monitoring layer's derived
status.

Saving an experiment also wires up logging into its directory (see
:meth:`Experiment.init_logging`), so every experiment automatically gets logging (a
per-writer log under ``<root>/.logs/``).
"""

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from loguru import logger

from exporgo._atomic import atomic_write_text
from exporgo.experiment.identity import (
    Identity,
    IdentityKey,
    IdentitySchema,
    IdentityValue,
)
from exporgo.experiment.resources import Dump, Resource, ResourceSpec
from exporgo.log import LogLevel, init_logger, read_log

if TYPE_CHECKING:
    import polars as pl

    from exporgo.datastore.arrays import ArrayStore, ArrayStoreSpec
    from exporgo.datastore.spec import StoreSpec
    from exporgo.datastore.store import Store

__all__ = ["CoverageReport", "Experiment", "ValidationReport"]

_CONFIG_NAME = "experiment.json"
_ENTITIES_NAME = "entities.jsonl"
_LOGS_NAME = ".logs"  # matches exporgo.log.sinks._LOGS_DIRNAME

_FORMAT_VERSION = 1
"""The experiment.json format this exporgo writes; loads refuse a file declaring a newer one."""

_KNOWN_KEYS = frozenset(
    {"format", "name", "identity", "resources", "stores", "array_stores", "dumps"}
)
"""The experiment.json top-level keys this exporgo understands (others warn on load)."""


def _require_store_type(experiment_name: str) -> "type[Store]":
    """Import and return :class:`~exporgo.datastore.store.Store`, or explain the extra.

    Args:
        experiment_name: The experiment being loaded, for the error message.

    Returns:
        The :class:`~exporgo.datastore.store.Store` class.

    Raises:
        ImportError: If the datastore layer is not installed, with the install hint.
    """
    try:
        from exporgo.datastore.store import Store
    except ImportError as error:
        msg = (
            f"Experiment {experiment_name!r} declares stores or array stores, which require "
            f"the datastore layer; install the datastore extra (exporgo[datastore])."
        )
        raise ImportError(msg) from error
    return Store


@dataclass(frozen=True)
class ValidationReport:
    """Outcome of :meth:`Experiment.validate` — whether each identity's indicated files exist.

    A closed-world, existence-only snapshot: each registered identity's declared resources
    are bucketed by whether the file or folder they point at exists on disk. Holds no live
    handles, so it is safe to store or diff across runs.

    Attributes:
        present: ``(identity, component_name)`` pairs whose indicated path exists.
        missing: ``(identity, component_name)`` pairs whose indicated path is absent.

    Note:
        See the "Coverage and validation" explanation for the closed- vs open-world
        distinction and how this differs from :class:`CoverageReport`.
    """

    present: tuple[tuple[Identity, str], ...]
    missing: tuple[tuple[Identity, str], ...]

    @property
    def is_complete(self) -> bool:
        """True when every registered identity's resources exist on disk."""
        return not self.missing


@dataclass(frozen=True)
class CoverageReport:
    """Which identities each component (store/resource) contains, derived on demand.

    Generalizes :class:`ValidationReport` across stores and resources -- the outcome of both
    :meth:`Experiment.coverage` (stores and array stores) and :meth:`Experiment.discover` (resources).

    Attributes:
        present: ``(identity, component_name)`` pairs where the registered identity is
            contained in that component.
        missing: ``(identity, component_name)`` pairs where a registered identity is
            absent from that component.
        unregistered: ``(identity, component_name)`` pairs for identities physically present
            on disk but not registered in the experiment.

    Note:
        See the "Coverage and validation" explanation for closed- vs open-world reporting
        (resources closed-world; stores open-world, surfacing drift as
        ``unregistered``).
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

    def __str__(self) -> str:
        """Render a grouped, human-readable summary (a header line plus per-status lists).

        Lists the actionable buckets first (``missing`` then ``unregistered``) and finally
        ``present``, each as ``component: identity`` lines sorted by component then identity.
        For programmatic filtering, prefer :meth:`to_polars`.
        """
        state = "complete" if self.is_complete else "incomplete"
        header = (
            f"CoverageReport: {len(self.present)} present, {len(self.missing)} missing, "
            f"{len(self.unregistered)} unregistered ({state})"
        )
        lines = [header]
        for label, pairs in (
            ("missing", self.missing),
            ("unregistered", self.unregistered),
            ("present", self.present),
        ):
            if not pairs:
                continue
            lines.append(f"  {label}:")
            lines.extend(
                f"    {component}: {identity.as_path()}"
                for identity, component in sorted(
                    pairs, key=lambda pair: (pair[1], pair[0].as_path())
                )
            )
        return "\n".join(lines)

    def to_polars(self) -> "pl.DataFrame":
        """Materialize the report as a tidy, long-format :class:`polars.DataFrame`.

        Each ``(identity, component)`` pair becomes one row: the identity's keys explode
        into their own columns (null-filled where a partial identity lacks a key), followed
        by a ``component`` column and a ``status`` column
        (``"present"`` / ``"missing"`` / ``"unregistered"``).

        Returns:
            A DataFrame with one row per ``(identity, component)`` pair, columns
            ``[*identity_keys, "component", "status"]``.

        Raises:
            ImportError: If polars is not installed (it ships with the ``datastore`` extra).

        Note:
            See the "Validate and report on an experiment" how-to for filtering and pivoting.
        """
        try:
            import polars as pl
        except ImportError as error:
            msg = (
                "CoverageReport.to_polars() requires polars; install the datastore extra "
                "(exporgo[datastore])."
            )
            raise ImportError(msg) from error

        buckets = (
            ("present", self.present),
            ("missing", self.missing),
            ("unregistered", self.unregistered),
        )
        key_order: list[str] = []
        for _status, pairs in buckets:
            for identity, _component in pairs:
                for key in identity.keys:
                    if key not in key_order:
                        key_order.append(key)
        columns = [*key_order, "component", "status"]
        data: dict[str, list[object]] = {column: [] for column in columns}
        for status, pairs in buckets:
            for identity, component in pairs:
                values = identity.to_dict()
                for key in key_order:
                    data[key].append(values.get(key))
                data["component"].append(component)
                data["status"].append(status)
        return pl.DataFrame(data)


class Experiment:
    """An experiment: an identity coordinate system, registered identities, and their components.

    The data-side unit, living at the data root on the lab server: one root, one
    identity schema, one store catalog. A workspace's ``experiments/<name>/`` folder
    (the Rust CLI side) merely points at this root.
    """

    def __init__(
        self,
        name: str,
        root: str | Path,
        identity: Iterable[str | IdentityKey] | IdentitySchema | None = None,
    ) -> None:
        """Create an experiment.

        Args:
            name: A human-readable experiment name.
            root: The experiment's root directory on disk.
            identity: The identity keys (1-3), an :class:`IdentitySchema`, or ``None``
                to default to ``["Subject"]``.
        """
        self.name: str = name
        self.root: Path = Path(root)
        self.identity = self._coerce_schema(identity)
        self._entities: list[Identity] = []
        self._entity_index: set[Identity] = set()
        self._resources: dict[str, ResourceSpec] = {}
        self._stores: dict[str, StoreSpec] = {}
        self._array_stores: dict[str, ArrayStoreSpec] = {}
        self._dumps: list[str] = []

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
        """Return an unambiguous representation of the experiment for debugging."""
        return (
            f"{type(self).__name__}(name={self.name!r}, root={self.root!r}, "
            f"identity={self.identity.names!r})"
        )

    def __str__(self) -> str:
        """Return a concise one-line human-readable summary of the experiment."""
        keys = ", ".join(self.identity.names)
        return (
            f"Experiment {self.name!r} [{keys}]: {len(self._entities)} identities, "
            f"{len(self._resources)} resources, {len(self._stores)} stores, "
            f"{len(self._array_stores)} array stores, {len(self._dumps)} dumps"
        )

    def print(self) -> None:
        """Print a multi-line summary of the experiment's declared contents to stdout.

        Reports the experiment name and root, its identity keys, and the counts (and names)
        of registered identities, declared resources, stores, array stores, and dumps.
        """
        resources = ", ".join(sorted(self._resources)) or "(none)"
        stores = ", ".join(sorted(self._stores)) or "(none)"
        array_stores = ", ".join(sorted(self._array_stores)) or "(none)"
        dumps = ", ".join(sorted(self._dumps)) or "(none)"
        keys = ", ".join(self.identity.names)
        lines = [
            f"Experiment {self.name!r}",
            f"  root:         {self.root}",
            f"  identity:     {keys}",
            f"  identities:   {len(self._entities)} registered",
            f"  resources:    {len(self._resources)} ({resources})",
            f"  stores:       {len(self._stores)} ({stores})",
            f"  array stores: {len(self._array_stores)} ({array_stores})",
            f"  dumps:        {len(self._dumps)} ({dumps})",
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
    def array_stores(self) -> dict[str, "ArrayStoreSpec"]:
        """The declared array-store specs, keyed by name (a copy; safe to mutate)."""
        return dict(self._array_stores)

    def register(self, **values: IdentityValue) -> Identity:
        """Register an identity the experiment should contain (a declared expectation).

        Registration records what *should* exist; it never touches the filesystem. This
        declared expectation is what lets :meth:`validate` detect missing data.
        Re-registering an identical identity is a no-op (identities are de-duplicated).

        Args:
            **values: One value per identity key, keyed by key name (e.g.
                ``Subject="m01", Session=1``); each is coerced to its key's dtype.

        Returns:
            The registered :class:`~exporgo.experiment.identity.Identity`.

        Raises:
            ValueError: If a key is missing or an unexpected key is supplied.
        """
        identity = self.identity.identity(**values)
        if identity not in self._entity_index:
            self._entities.append(identity)
            self._entity_index.add(identity)

        msg = f"Registered {values} to {self.name}"
        logger.info(msg)

        return identity

    def declare_resource(self, name: str, template: str) -> Resource:
        """Declare a named resource located by a path template over the identity keys.

        A resource is a file/folder the experiment expects at each identity (e.g. ``"raw"``,
        ``"suite2p"``). Its ``template`` uses ``{KeyName}`` placeholders drawn from any
        subset of the experiment's identity keys and is resolved against the experiment root by
        :meth:`path` / :meth:`resource` and :meth:`validate`.

        Args:
            name: The resource's name (its handle in :meth:`resource` / :meth:`path`).
            template: A path template over the identity keys, e.g.
                ``"{Subject}/{Session}/behavior.csv"``.

        Returns:
            The root-bound :class:`~exporgo.experiment.resources.Resource` handle, ready to
            resolve paths and check existence (the declared spec is available via
            :attr:`resources`).

        Raises:
            ValueError: If the template references keys not in the experiment's identity.
        """
        spec = ResourceSpec(name=name, template=template)
        unknown = [key for key in spec.placeholders if key not in self.identity.names]
        if unknown:
            msg = (
                f"Resource {name!r} template uses unknown identity keys {unknown}; "
                f"experiment identity keys are {list(self.identity.names)}."
            )
            raise ValueError(msg)
        self._resources[name] = spec

        msg = f"Declared the resource {spec}"
        logger.info(msg)

        return self.resource(name)

    def resource(self, name: str) -> Resource:
        """Return the root-bound :class:`~exporgo.experiment.resources.Resource` handle.

        Binds the named resource's declaration to the experiment root and identity schema, so
        you can resolve paths (:meth:`Resource.path`) and check existence
        (:meth:`Resource.exists`) for specific identity values. This is the resource
        counterpart of :meth:`store`.

        Args:
            name: The name of a previously declared resource.

        Returns:
            The :class:`~exporgo.experiment.resources.Resource` bound to this experiment's root.

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
        return Resource(self.root, spec, self.identity, exclude=self._owned_names())

    def _owned_names(self) -> frozenset[str]:
        """Top-level names under the root owned by the experiment itself, never identities.

        Covers the experiment's manifest JSON, its entity sidecar, its log directory, and
        every declared store, array-store, and dump directory, so resource discovery
        never mistakes the experiment's own artifacts for identity candidates.
        """
        return frozenset(
            {_CONFIG_NAME, _ENTITIES_NAME, _LOGS_NAME}
            | set(self._stores)
            | set(self._array_stores)
            | set(self._dumps)
        )

    def path(self, resource: str, **values: IdentityValue) -> Path:
        """Resolve the on-disk path of ``resource`` for the given identity values.

        Shorthand for ``self.resource(resource).path(**values)`` — the terse one-shot for
        when you just need the location. The path is returned whether or not it exists;
        use :meth:`validate` to check existence.

        Args:
            resource: The name of a previously declared resource.
            **values: One value per identity key, keyed by key name.

        Returns:
            The resolved path under the experiment root.

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
    ) -> "Store":
        """Declare a datastore component; partition keys default to the identity keys.

        Args:
            name: The store's name (also its subdirectory under the experiment root).
            columns: The store's ``column -> polars dtype`` schema (must include the
                partition keys); any polars dtype, at full fidelity.
            partition_keys: Columns to partition by (1-3); defaults to the experiment's
                identity keys.
            sort_column: Optional column to sort by within partitions.
            max_rows_per_file: Write-time cap on rows per Parquet fragment (``None`` = no
                exporgo-imposed limit). Part of the declaration, so it survives save/load.
            max_rows_per_group: Write-time cap on rows per row group (``None`` = pyarrow's
                default). Part of the declaration, so it survives save/load.

        Returns:
            The :class:`~exporgo.datastore.store.Store` bound to ``<root>/<name>``, ready
            to write and scan (the declared spec is available via :attr:`stores`).
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

        return self.store(name)

    def store(self, name: str) -> "Store":
        """Return the :class:`~exporgo.datastore.store.Store` for a declared component.

        Binds the store's declared spec to ``<root>/<name>`` so it can be written to and
        scanned. The return type lives in the datastore extra, so it is imported lazily;
        ``import exporgo.experiment`` alone does not pull in the datastore layer.

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

    def declare_array_store(
        self,
        name: str,
        *,
        dims: Mapping[str, Any],
        dtype: Any,
        partition_keys: Sequence[str] | None = None,
        max_rows_per_file: int | None = 25_000_000,
        max_rows_per_group: int | None = None,
    ) -> "ArrayStore":
        """Declare an array-store component (one N-D array per identity, loaded as xarray).

        An array store holds a single dense array per identity as a NumPy ``.npy`` blob, paired
        with a coordinate catalog. Partition keys default to the experiment's identity keys, so a
        partition is an identity.

        Args:
            name: The array store's name (also its subdirectory under the experiment root).
            dims: An ordered ``{dimension: coord dtype}`` mapping giving the array's axis order;
                each value is the polars dtype of that dimension's coordinate vector, or ``None``
                for a positional (unlabelled) dimension.
            dtype: The array's element dtype (anything :func:`numpy.dtype` accepts, e.g.
                ``numpy.float32``); the write casts to it.
            partition_keys: Columns to partition by (1-3); defaults to the experiment's identity keys.
            max_rows_per_file: Write-time cap on rows per coordinate-catalog fragment (``None`` =
                no exporgo-imposed limit). Part of the declaration, so it survives save/load.
            max_rows_per_group: Write-time cap on rows per coordinate-catalog row group
                (``None`` = pyarrow's default). Part of the declaration, so it survives
                save/load.

        Returns:
            The :class:`~exporgo.datastore.arrays.ArrayStore` bound to ``<root>/<name>``.
        """
        from exporgo.datastore.arrays import ArrayStoreSpec, coord_dtype_for_label

        keys = (
            tuple(partition_keys) if partition_keys is not None else self.identity.names
        )
        key_by_name = {key.name: key for key in self.identity.keys}
        partition_dtypes = {
            key: coord_dtype_for_label(
                key_by_name[key].dtype if key in key_by_name else "str"
            )
            for key in keys
        }
        spec = ArrayStoreSpec(
            name=name,
            dims=dict(dims),
            dtype=dtype,
            partition_keys=keys,
            partition_dtypes=partition_dtypes,
            max_rows_per_file=max_rows_per_file,
            max_rows_per_group=max_rows_per_group,
        )
        self._array_stores[name] = spec

        msg = f"Declared the array store {name!r}"
        logger.info(msg)

        return self.array_store(name)

    def array_store(self, name: str) -> "ArrayStore":
        """Return the :class:`~exporgo.datastore.arrays.ArrayStore` for a declared component.

        Binds the array store's declared spec to ``<root>/<name>`` so it can be written to and
        loaded. The return type lives in the datastore extra, so it is imported lazily;
        ``import exporgo.experiment`` alone does not pull in the datastore layer.

        Args:
            name: The name of a previously declared array store.

        Returns:
            The :class:`~exporgo.datastore.arrays.ArrayStore` bound to ``<root>/<name>``.

        Raises:
            KeyError: If no array store with that name has been declared.
        """
        from exporgo.datastore.arrays import ArrayStore

        try:
            spec = self._array_stores[name]
        except KeyError:
            msg = (
                f"No array store named {name!r}; "
                f"declared array stores: {sorted(self._array_stores)}"
            )
            raise KeyError(msg) from None
        return ArrayStore(self.root / name, spec)

    def declare_dump(self, name: str) -> Dump:
        """Declare an experiment-global dump component and return its handle.

        A dump records one root and the files under it, keyed by each file's path relative
        to that root -- for assets that belong to the whole experiment rather than to any one
        identity (an atlas, a README, a shared lookup table). The recorded paths live in a
        sidecar ``<root>/<name>/_dump.json`` written by the handle.

        Args:
            name: The dump's name (also its subdirectory under the experiment root).

        Returns:
            The :class:`~exporgo.experiment.resources.Dump` handle bound to ``<root>/<name>``.
        """
        if name not in self._dumps:
            self._dumps.append(name)

        msg = f"Declared the dump {name!r}"
        logger.info(msg)

        return self.dump(name)

    def dump(self, name: str) -> Dump:
        """Return the :class:`~exporgo.experiment.resources.Dump` handle for a component.

        Args:
            name: The name of a previously declared dump.

        Returns:
            The :class:`~exporgo.experiment.resources.Dump` bound to ``<root>/<name>``.

        Raises:
            KeyError: If no dump with that name has been declared.
        """
        if name not in self._dumps:
            msg = f"No dump named {name!r}; declared dumps: {sorted(self._dumps)}"
            raise KeyError(msg)
        return Dump(self.root / name, name)

    @property
    def dumps(self) -> dict[str, Dump]:
        """The declared dumps, keyed by name (the experiment-global :class:`Dump` handles)."""
        return {name: self.dump(name) for name in self._dumps}

    def validate(self) -> ValidationReport:
        """Check that each registered identity's indicated files still exist on disk.

        For every registered identity, tests each declared resource (does its resolved
        template path exist?), bucketing the ``(identity, component)`` pair as ``present`` or
        ``missing``. Nothing is cached, so the report always reflects the tree at call time.
        Stores are out of scope; use :meth:`coverage` for store membership.

        Returns:
            A :class:`ValidationReport` partitioning the pairs into ``present`` and
            ``missing``.

        Note:
            Existence-only (file contents are never read). See the "Coverage and
            validation" explanation for validate vs coverage.
        """
        report = self._reconcile(
            (name, self.identity.names, self.identities(resource=name))
            for name in self._resources
        )
        return ValidationReport(present=report.present, missing=report.missing)

    def identities(
        self,
        *,
        store: str | None = None,
        resource: str | None = None,
        array_store: str | None = None,
    ) -> set[Identity]:
        """Return the identities in one declared store, array store, or resource.

        Exactly one target must be given. A **store** and an **array store** are reported
        open-world (their manifest partitions), so they may include identities never
        registered in the experiment. A **resource** is reported closed-world -- the registered
        identities whose resolved file exists on disk (there is no scan for unregistered
        files; that is :meth:`discover`'s role).

        Args:
            store: The name of a declared store to inventory, or ``None``.
            resource: The name of a declared resource to inventory, or ``None``.
            array_store: The name of a declared array store to inventory, or ``None``.

        Returns:
            The contained :class:`~exporgo.experiment.identity.Identity` objects. Store and
            array-store identities are built over the component's partition keys; resource
            identities are the registered identities that are present.

        Raises:
            ValueError: If not exactly one target is given.
            KeyError: If no store/array store/resource with that name has been declared.
        """
        provided = [name for name in (store, resource, array_store) if name is not None]
        if len(provided) != 1:
            msg = "identities() requires exactly one of 'store', 'resource', 'array_store'."
            raise ValueError(msg)
        if store is not None:
            component = self.store(store)
            return {
                self._identity_from_partition(component.spec.partition_keys, partition)
                for partition in component.manifest().partitions()
            }
        if array_store is not None:
            array_component = self.array_store(array_store)
            return {
                self._identity_from_partition(
                    array_component.spec.partition_keys, partition
                )
                for partition in array_component.manifest().partitions()
            }
        assert resource is not None  # the only remaining option after the guard above
        handle = self.resource(resource)
        return {
            entity for entity in self._entities if handle.exists(**entity.to_dict())
        }

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

    def _reconcile(
        self,
        components: Iterable[tuple[str, tuple[str, ...], set[Identity]]],
    ) -> CoverageReport:
        """Bucket the registered identities against each component's contained set.

        The shared engine behind :meth:`validate`, :meth:`coverage`, and :meth:`discover`.
        For each ``(name, keys, contained)`` triple, every registered identity is projected
        onto ``keys`` (skipping identities that lack one of them) and classified as
        ``present`` or ``missing`` against ``contained``; any contained identity no
        registered identity projects onto is surfaced as ``unregistered`` drift, in
        ``as_path`` order.

        Args:
            components: ``(component_name, partition/placeholder keys, contained
                identities)`` triples. ``contained`` is sourced open- or closed-world by
                the caller (a store manifest, a resource existence check, or a reverse-
                resolved template).

        Returns:
            A :class:`CoverageReport` over the supplied components.
        """
        present: list[tuple[Identity, str]] = []
        missing: list[tuple[Identity, str]] = []
        unregistered: list[tuple[Identity, str]] = []
        for name, keys, contained in components:
            projected: set[Identity] = set()
            for identity in self._entities:
                projection = self._project(identity, keys)
                if projection is None:
                    continue
                projected.add(projection)
                bucket = present if projection in contained else missing
                bucket.append((identity, name))
            unregistered.extend(
                (extra, name)
                for extra in sorted(contained - projected, key=Identity.as_path)
            )
        return CoverageReport(
            present=tuple(present),
            missing=tuple(missing),
            unregistered=tuple(unregistered),
        )

    def _collect_contained(self) -> set[Identity]:
        """Union of identities physically present across every identity-bearing component.

        Sweeps resources (reverse-resolved from their templates) plus stores and array
        stores (their manifest partitions). Dumps have no identity and are not swept.
        """
        contained: set[Identity] = set()
        for resource_name in self._resources:
            contained |= self.resource(resource_name).discover()
        for store_name in self._stores:
            contained |= self.identities(store=store_name)
        for array_store_name in self._array_stores:
            contained |= self.identities(array_store=array_store_name)
        return contained

    def _register_full_key(self, identities: Iterable[Identity]) -> list[Identity]:
        """Register each not-yet-registered full-key identity; return the new ones.

        Subset-key partials (from a subset-key store or resource) cannot be registered and
        are skipped. Idempotent: already-registered identities are left untouched and
        omitted from the result, which is ordered by ``as_path``.
        """
        full = set(self.identity.names)
        newly: list[Identity] = []
        for identity in sorted(identities, key=Identity.as_path):
            if set(identity.keys) != full:
                continue  # partial identity (subset-key store/resource); cannot register
            canonical = self.identity.identity(**identity.to_dict())
            if canonical in self._entity_index:
                continue
            self.register(**identity.to_dict())
            newly.append(canonical)
        return newly

    def coverage(self) -> CoverageReport:
        """Report which registered identities each declared store/resource contains.

        Generalizes :meth:`validate` to cover resources (existence of the declared file) and
        stores and array stores (presence in the manifest), classifying every
        ``(registered identity, component)`` pair as present or missing. Identities present on
        disk but not registered by a store or array store are collected in
        :attr:`CoverageReport.unregistered` (a resource's on-disk-but-unregistered data is
        surfaced separately, by :meth:`discover`).

        Returns:
            A :class:`CoverageReport` over registered identities and declared components.

        Note:
            See the "Coverage and validation" explanation for closed- vs open-world drift.
        """
        components: list[tuple[str, tuple[str, ...], set[Identity]]] = [
            (name, self.identity.names, self.identities(resource=name))
            for name in self._resources
        ]
        components.extend(
            (name, spec.partition_keys, self.identities(store=name))
            for name, spec in self._stores.items()
        )
        components.extend(
            (name, spec.partition_keys, self.identities(array_store=name))
            for name, spec in self._array_stores.items()
        )
        return self._reconcile(components)

    def discover(self, *, register: bool = False) -> CoverageReport:
        """Scan the filesystem for resource identities and report the drift.

        Reverse-resolves each resource template (see
        :meth:`~exporgo.experiment.resources.Resource.discover`) to find which identities are
        physically present, surfacing on-disk-but-unregistered data as
        :attr:`CoverageReport.unregistered`. With ``register=True``, the discovered
        **full-key** identities are registered afterward; subset-key partials are reported
        but never registered. The returned report always reflects the **pre-bootstrap**
        state.

        Args:
            register: If ``True``, register the discovered full-key identities after
                building the report (a no-op for already-registered ones).

        Returns:
            A :class:`CoverageReport` over the declared resources, reflecting the registry
            as it stood *before* any bootstrapping.

        Note:
            Constant-template resources are skipped; stores are not scanned
            here. See the "Discover identities from an existing dataset" how-to.
        """
        components: list[tuple[str, tuple[str, ...], set[Identity]]] = []
        discovered: set[Identity] = set()
        for resource_name, spec in self._resources.items():
            keys = spec.placeholders
            if not keys:  # constant template: no identity to reverse-resolve
                continue
            contained = self.resource(resource_name).discover()
            discovered |= contained
            components.append((resource_name, keys, contained))
        report = self._reconcile(components)
        if register:
            self._register_full_key(discovered)
        return report

    def sync_registry(self) -> tuple[Identity, ...]:
        """Register every identity found in any declared component not yet registered.

        Sweeps every identity-bearing component for the identities physically present --
        resources (reverse-resolved from their templates, see
        :meth:`~exporgo.experiment.resources.Resource.discover`) plus stores and array stores
        (their manifest partitions) -- and registers each one the experiment does not already
        contain. Dumps have no identity and are never swept. Only **full-key** identities can
        be registered; subset-key partials are skipped. The sweep is idempotent:
        already-registered identities are left untouched and are not returned.

        Returns:
            The newly registered :class:`~exporgo.experiment.identity.Identity` objects, in
            ``as_path`` order (empty if every found identity was already registered).

        Note:
            The bulk, all-component companion to :meth:`discover`. See the "Discover
            identities from an existing dataset" how-to.
        """
        newly = self._register_full_key(self._collect_contained())
        msg = f"Auto-registered {len(newly)} new identities to {self.name}."
        logger.info(msg)
        return tuple(newly)

    def init_logging(
        self,
        *,
        name: str | None = None,
        log_level_console: LogLevel = LogLevel.INFO,
        log_level_custom: LogLevel | None = None,
    ) -> None:
        """Configure logging to write into this experiment's directory.

        Materializes the experiment root if needed and drives
        :func:`exporgo.log.init_logger` with ``base_directory`` set to the experiment root and
        ``file_stem`` set to the experiment name, so an experiment automatically has its own log
        file. Called automatically by :meth:`save`; call it directly to start logging into
        the experiment before the first save (e.g. when resuming an experiment via :meth:`load`).

        Writes into this writer's own directory ``<root>/.logs/<host>_<user>_<pid>/`` --
        ``<name>.log`` (INFO/WARNING) and ``<name>.exception.log`` (exceptions) -- and adds a
        colorized console sink. Concurrent writers each get their own directory, so they never
        share a file; :meth:`read_log` merges them. Like :func:`~exporgo.log.init_logger` it
        resets existing sinks, so repeated calls are safe and idempotent.

        Args:
            name: Loguru namespace to enable; ``None`` (the default) enables all
                namespaces, so the experiment log captures both exporgo's own records and your
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

    def read_log(self, *, exceptions: bool = False) -> str:
        """Return this experiment's log, merged across all writers in chronological order.

        Each process that logs into the experiment writes its own file under ``<root>/.logs/``;
        this reads them all and interleaves their records by timestamp (see
        :func:`exporgo.log.read_log`), so you get one timeline even when several people logged
        to the experiment at once.

        Args:
            exceptions: Read the exception logs instead of the primary logs.

        Returns:
            The merged log text (empty if nothing has been logged yet).
        """
        return read_log(self.root, file_stem=self.name, exceptions=exceptions)

    def save(self, *, init_logging: bool = True) -> Path:
        """Write the experiment's declaration to ``root/experiment.json`` and return that path.

        Registered entities are persisted separately, one JSON object per line, to
        ``root/entities.jsonl`` -- entity counts can grow far larger than the rest of the
        declaration, and keeping them out of ``experiment.json`` keeps that file small and its
        parse cost independent of how many identities are registered.

        By default, saving also initializes logging into the experiment root (see
        :meth:`init_logging`), so a saved experiment automatically gets logging (a per-writer
        log under ``<root>/.logs/``, readable merged via :meth:`read_log`). The **first**
        save (when ``experiment.json`` does not yet exist) records a "created" line with the
        creation date; subsequent saves record a plain "saved" line.

        Warning:
            ``init_logging=True`` (the default) reconfigures loguru's **process-global**
            logger: every existing sink -- including sinks your application or another
            library added -- is removed before the experiment's sinks are attached. When
            embedding exporgo in a host application that manages its own logging, pass
            ``init_logging=False`` to leave the global logger untouched.

        Args:
            init_logging: Whether to (re)initialize logging into the experiment root after
                saving. ``True`` (the default) calls :meth:`init_logging`, which resets
                all loguru sinks process-wide; ``False`` saves without touching logging.

        Returns:
            The path of the written ``experiment.json``.
        """
        data: dict[str, object] = {
            "format": _FORMAT_VERSION,
            "name": self.name,
            "identity": [
                {"name": key.name, "dtype": key.dtype} for key in self.identity.keys
            ],
            "resources": {
                name: resource.template for name, resource in self._resources.items()
            },
        }
        stores: dict[str, dict[str, object]] = {}
        for store_name, spec in self._stores.items():
            entry: dict[str, object] = {
                "partition_keys": list(spec.partition_keys),
                "max_rows_per_file": spec.max_rows_per_file,
                "max_rows_per_group": spec.max_rows_per_group,
            }
            if spec.sort_column is not None:
                entry["sort_column"] = spec.sort_column
            stores[store_name] = entry
        data["stores"] = stores
        array_stores: dict[str, dict[str, object]] = {}
        for array_store_name, array_spec in self._array_stores.items():
            array_stores[array_store_name] = {
                "dtype": str(array_spec.numpy_dtype),
                "partition_keys": list(array_spec.partition_keys),
                "dims": list(array_spec.dim_names),
                "max_rows_per_file": array_spec.max_rows_per_file,
                "max_rows_per_group": array_spec.max_rows_per_group,
            }
        data["array_stores"] = array_stores
        data["dumps"] = list(self._dumps)
        self.root.mkdir(parents=True, exist_ok=True)
        config_path = self.root / _CONFIG_NAME
        is_first_save = not config_path.exists()  # before we (over)write it below
        atomic_write_text(config_path, json.dumps(data, indent=2))
        entities_text = "".join(
            f"{json.dumps(identity.to_dict())}\n" for identity in self._entities
        )
        atomic_write_text(self.root / _ENTITIES_NAME, entities_text)
        for store_name in self._stores:
            self.store(store_name).write_schema()  # persist each store's schema anchor
        for array_store_name in self._array_stores:
            # persist each array store's coordinate-catalog schema anchor
            self.array_store(array_store_name).write_schema()
        if init_logging:
            self.init_logging()
        if is_first_save:
            creation_date = datetime.now(UTC).isoformat(timespec="seconds")
            msg = f"Experiment {self.name!r} created {creation_date} (saved to {config_path})."
        else:
            msg = f"Experiment {self.name!r} saved to {config_path}."
        logger.info(msg)
        return config_path

    @classmethod
    def load(cls, root: str | Path) -> Self:
        """Reconstruct an experiment from ``root/experiment.json`` (the declaration only).

        Restores the declared structure — identity keys, registered identities, resource
        templates, and store specs — but not the data or any derived status, which are
        re-read from the filesystem on demand (filesystem = truth). Registered entities are
        read back from the ``root/entities.jsonl`` sidecar written by :meth:`save` (absent if
        none were ever saved). Loading does *not* reconfigure logging (it adds no sinks); it
        only emits an access log record, which is captured if logging is already configured.
        Call :meth:`init_logging` to resume logging into a loaded experiment.

        Args:
            root: The experiment root directory containing ``experiment.json``.

        Returns:
            The reconstructed :class:`Experiment`.

        Raises:
            FileNotFoundError: If ``root/experiment.json`` does not exist.
            ValueError: If ``experiment.json`` declares a format newer than this exporgo
                understands (upgrade exporgo to load it).
            ImportError: If the experiment declares stores or array stores but the datastore
                extra is not installed (``pip install exporgo[datastore]``).
        """
        root = Path(root)
        data = json.loads((root / _CONFIG_NAME).read_text(encoding="utf-8"))
        # An absent "format" key means a legacy (format 1) file; an explicit
        # null does not, so membership is tested rather than data.get().
        format_version = data["format"] if "format" in data else _FORMAT_VERSION
        if (
            not isinstance(format_version, int)
            or isinstance(format_version, bool)
            or format_version > _FORMAT_VERSION
        ):
            # A non-integer format is refused too: it can only come from a
            # newer (or corrupted) writer, and silently treating it as legacy
            # would hide that.
            msg = (
                f"{root / _CONFIG_NAME} declares format {format_version!r}, but this "
                f"exporgo understands only integer formats up to {_FORMAT_VERSION}; "
                f"upgrade exporgo to load this experiment."
            )
            raise ValueError(msg)
        unknown = sorted(set(data) - _KNOWN_KEYS)
        if unknown:
            msg = (
                f"{root / _CONFIG_NAME} carries unknown top-level keys {unknown}; "
                f"they are ignored and will be dropped by the next save()."
            )
            logger.warning(msg)
        keys = [IdentityKey.model_validate(spec) for spec in data["identity"]]
        experiment = cls(name=data["name"], root=root, identity=keys)
        for name, template in data.get("resources", {}).items():
            experiment.declare_resource(name, template)
        stores_data = data.get("stores", {})
        array_stores_data = data.get("array_stores", {})
        if stores_data:
            store_type = _require_store_type(data["name"])
            for store_name, entry in stores_data.items():
                experiment.declare_store(
                    store_name,
                    store_type.read_schema(root / store_name),
                    partition_keys=entry["partition_keys"],
                    sort_column=entry.get("sort_column"),
                    max_rows_per_file=entry.get("max_rows_per_file", 25_000_000),
                    max_rows_per_group=entry.get("max_rows_per_group"),
                )
        if array_stores_data:
            store_type = _require_store_type(data["name"])
            for array_store_name, entry in array_stores_data.items():
                # The coordinate-catalog anchor is authoritative for each labelled
                # dimension's coordinate dtype; experiment.json fixes the axis order and which
                # dimensions are positional (absent from the anchor).
                coord_schema = store_type.read_schema(
                    root / array_store_name / "_coords"
                )
                dims = {
                    dim: (coord_schema[dim].inner if dim in coord_schema else None)
                    for dim in entry["dims"]
                }
                experiment.declare_array_store(
                    array_store_name,
                    dims=dims,
                    dtype=entry["dtype"],
                    partition_keys=entry["partition_keys"],
                    max_rows_per_file=entry.get("max_rows_per_file", 25_000_000),
                    max_rows_per_group=entry.get("max_rows_per_group"),
                )
        for dump_name in data.get("dumps", []):
            experiment.declare_dump(dump_name)
        entities_path = root / _ENTITIES_NAME
        if entities_path.exists():
            for line in entities_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    experiment.register(**json.loads(line))
        msg = f"Experiment {experiment.name!r} accessed (loaded from {root / _CONFIG_NAME})."
        logger.info(msg)
        return experiment
