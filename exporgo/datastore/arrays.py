"""Array stores: one N-D array per identity, paired with a coordinate catalog.

An :class:`ArrayStore` is the datastore's second component kind, beside the tabular
:class:`~exporgo.datastore.store.Store`. Where a tabular store holds columnar rows queried
as a :class:`polars.LazyFrame`, an array store holds **exactly one dense array per identity**
-- calcium traces ``[unit, time]``, an imaging tensor, deconvolved spikes -- stored as a NumPy
``.npy`` blob and loaded as an :class:`xarray.DataArray`.

Each identity's array lives at a Hive-partitioned path (``Subject=m01/Session=1/data-<uuid>.npy``)
tracked by the same append-only ``_manifest/`` log the tabular store uses, so writes are
multi-writer safe and overwrite tombstones the prior blob. The **coordinate catalog** -- the
actual coordinate vectors (timestamps, unit indices) -- is a nested tabular store under
``_coords/``: one row per identity, one list-valued column per labelled dimension. A ``.npy``
already records its own shape and element dtype, so the catalog stores coordinates and nothing
scalar.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self
from uuid import uuid4

import numpy as np
import polars as pl
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from exporgo.datastore import _partition
from exporgo.datastore.manifest import FragmentEntry, Manifest, append_manifest_log
from exporgo.datastore.spec import StoreSpec
from exporgo.datastore.store import Store

if TYPE_CHECKING:
    import xarray as xr

__all__ = ["ArrayStore", "ArrayStoreSpec"]

_MIN_PARTITION_KEYS = 1
_MAX_PARTITION_KEYS = 3

_MANIFEST_DIR = "_manifest"
_COORDS_DIR = "_coords"
_DATA_PREFIX = "data-"

_NESTED_DTYPES = (pl.List, pl.Array, pl.Struct)
"""polars dtypes that cannot serve as a partition key or a coordinate element type."""

_IDENTITY_DTYPES: dict[str, Any] = {
    "str": pl.String,
    "int": pl.Int64,
    "bool": pl.Boolean,
}
"""Maps an :class:`~exporgo.study.identity.IdentityKey` dtype label to a polars dtype."""


def coord_dtype_for_label(label: str) -> Any:
    """Return the polars partition-column dtype for an identity-key dtype label.

    Args:
        label: An identity-key dtype label (``"str"``, ``"int"``, or ``"bool"``).

    Returns:
        The corresponding polars dtype used for that partition column in the catalog.
    """
    return _IDENTITY_DTYPES[label]


class ArrayStoreSpec(BaseModel):
    """Declares one array-store component: its dimensions, element dtype, and keys.

    An array store holds exactly **one N-D array per identity**, stored as a NumPy ``.npy``
    blob and loaded as an :class:`xarray.DataArray`. ``dims`` is an *ordered* mapping from each
    dimension name to the polars dtype of its coordinate vector, or ``None`` for a positional
    (unlabelled) dimension; its order is the array's axis order. ``dtype`` is the array's element
    dtype (a NumPy dtype). ``partition_keys`` (1-3) drive the on-disk Hive layout exactly as in
    :class:`~exporgo.datastore.spec.StoreSpec`, and ``partition_dtypes`` gives each key's polars
    dtype for the coordinate catalog's partition columns.

    Example:
        >>> import numpy as np, polars as pl
        >>> spec = ArrayStoreSpec(
        ...     name="neural",
        ...     dims={"unit": pl.Int64, "time": pl.Float64},
        ...     dtype=np.dtype("float32"),
        ...     partition_keys=("Subject", "Session"),
        ...     partition_dtypes={"Subject": pl.String, "Session": pl.Int64},
        ... )
        >>> spec.dim_names
        ('unit', 'time')
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, arbitrary_types_allowed=True
    )

    name: str
    dims: dict[str, Any]
    dtype: Any
    partition_keys: tuple[str, ...]
    partition_dtypes: dict[str, Any]
    max_rows_per_file: int | None = Field(default=25_000_000, ge=0)
    max_rows_per_group: int | None = Field(default=None, ge=0)

    @field_validator("dtype")
    @classmethod
    def _normalize_dtype(cls, value: Any) -> np.dtype:
        """Coerce the declared element dtype to a :class:`numpy.dtype`."""
        return np.dtype(value)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Enforce non-empty dims, 1-3 scalar partition keys disjoint from the dims."""
        if not self.dims:
            msg = "An array store must declare at least one dimension."
            raise ValueError(msg)
        count = len(self.partition_keys)
        if not _MIN_PARTITION_KEYS <= count <= _MAX_PARTITION_KEYS:
            msg = (
                f"An array store needs {_MIN_PARTITION_KEYS}-{_MAX_PARTITION_KEYS} "
                f"partition keys, got {count}."
            )
            raise ValueError(msg)
        if len(set(self.partition_keys)) != count:
            msg = f"Partition keys must be unique, got {list(self.partition_keys)}."
            raise ValueError(msg)
        missing = [
            key for key in self.partition_keys if key not in self.partition_dtypes
        ]
        if missing:
            msg = f"Partition keys without a declared dtype: {missing}."
            raise ValueError(msg)
        clash = [key for key in self.partition_keys if key in self.dims]
        if clash:
            msg = f"Partition keys must not also be dimensions: {clash}."
            raise ValueError(msg)
        self._reject_nested_coord_dtypes()
        return self

    def _reject_nested_coord_dtypes(self) -> None:
        """Reject nested (List/Array/Struct) dtypes for coordinates or partition keys."""
        nested_coords = [
            dim
            for dim, dtype in self.dims.items()
            if dtype is not None and isinstance(dtype, _NESTED_DTYPES)
        ]
        if nested_coords:
            msg = (
                f"Coordinate dtypes must be scalar; these are nested: {nested_coords}."
            )
            raise ValueError(msg)
        nested_keys = [
            key
            for key in self.partition_keys
            if isinstance(self.partition_dtypes[key], _NESTED_DTYPES)
        ]
        if nested_keys:
            msg = f"Partition keys must be scalar; these are nested: {nested_keys}."
            raise ValueError(msg)

    @property
    def dim_names(self) -> tuple[str, ...]:
        """The declared dimension names, in axis order."""
        return tuple(self.dims)

    @property
    def labelled_dims(self) -> tuple[str, ...]:
        """The dimensions that carry a coordinate vector, in axis order."""
        return tuple(dim for dim, dtype in self.dims.items() if dtype is not None)

    @property
    def numpy_dtype(self) -> np.dtype:
        """The array's element dtype as a :class:`numpy.dtype`."""
        return self.dtype

    def coord_spec(self) -> StoreSpec:
        """Build the :class:`~exporgo.datastore.spec.StoreSpec` for the coordinate catalog.

        The catalog is a plain tabular store whose columns are the partition keys followed by
        one :class:`polars.List` column per labelled dimension, partitioned by the same keys.

        Returns:
            The coordinate catalog's :class:`~exporgo.datastore.spec.StoreSpec`.
        """
        columns: dict[str, Any] = {
            key: self.partition_dtypes[key] for key in self.partition_keys
        }
        for dim in self.labelled_dims:
            columns[dim] = pl.List(self.dims[dim])
        return StoreSpec(
            name=f"{self.name}/{_COORDS_DIR}",
            columns=columns,
            partition_keys=self.partition_keys,
            max_rows_per_file=self.max_rows_per_file,
            max_rows_per_group=self.max_rows_per_group,
        )


class ArrayStore:
    """One array-store component: a per-identity ``.npy`` array plus a coordinate catalog.

    ``write`` stores an identity's N-D array as a Hive-partitioned ``.npy`` blob (recorded in an
    append-only manifest) alongside its coordinate vectors in a nested tabular catalog. ``load``
    pairs the two back into an :class:`xarray.DataArray`.
    """

    def __init__(self, root: str | Path, spec: ArrayStoreSpec) -> None:
        """Bind an array store to its root directory and specification.

        Args:
            root: The directory holding this component's ``.npy`` blobs and coordinate catalog.
            spec: The array store's declared dimensions, element dtype, and partition keys.
        """
        self.root = Path(root)
        self.spec = spec
        self._coords = Store(self.root / _COORDS_DIR, spec.coord_spec())

    def write(
        self,
        data: Any,
        *,
        coords: dict[str, Any] | None = None,
        mode: Literal["unique", "overwrite"] = "unique",
        **identity: Any,
    ) -> None:
        """Store one identity's array and its coordinate vectors.

        The array is cast to the declared element dtype and written as a Hive-partitioned
        ``.npy`` blob; its coordinate vectors are written as a one-row entry in the coordinate
        catalog. An array store holds a single array per identity, so there is no ``"append"``
        mode.

        Modes:

        - ``"unique"`` (default): refuse the write if this identity already has an array --
          fail loud rather than silently clobber.
        - ``"overwrite"``: replace this identity's array (the prior blob is tombstoned) and its
          coordinate row.

        Args:
            data: The array-like payload; its rank must equal the number of declared dimensions.
            coords: A ``{dimension: 1-D vector}`` mapping supplying every labelled dimension's
                coordinate; each vector's length must match that axis. ``None`` is allowed only
                when no dimension is labelled.
            mode: ``"unique"`` to refuse an existing identity, ``"overwrite"`` to replace it.
            **identity: One value per partition key, keyed by key name.

        Raises:
            ValueError: If the identity keys, array rank, element handling, or coordinates do
                not match the declaration, or if ``mode="unique"`` and the identity exists.
        """
        array = np.asarray(data, dtype=self.spec.numpy_dtype)
        self._validate_identity(identity)
        if array.ndim != len(self.spec.dims):
            msg = (
                f"Array store {self.spec.name!r} expects a {len(self.spec.dims)}-D array "
                f"(dims {self.spec.dim_names}), got a {array.ndim}-D array."
            )
            raise ValueError(msg)
        supplied = coords or {}
        self._validate_coords(supplied, array.shape)
        self.root.mkdir(parents=True, exist_ok=True)
        target = _partition.tuple_of_identity(self.spec.partition_keys, identity)
        if mode == "unique" and target in self._existing_partitions():
            pretty = dict(zip(self.spec.partition_keys, target, strict=True))
            msg = (
                f"Array store {self.spec.name!r} already contains identity {pretty}; "
                f"refusing to write (mode='unique')."
            )
            raise ValueError(msg)
        self._write_coords(identity, supplied)
        if mode == "overwrite":
            self._remove_identity(target)
        relative = self._write_array(identity, array)
        entry = FragmentEntry(
            path=relative,
            partition=_partition.dict_of_identity(self.spec.partition_keys, identity),
            rows=int(array.size),
            written=datetime.now(UTC).isoformat(),
        )
        append_manifest_log(self.root / _MANIFEST_DIR, added=[entry])
        pretty = _partition.dict_of_identity(self.spec.partition_keys, identity)
        msg = (
            f"Wrote a {array.shape} {array.dtype} array for identity "
            f"{pretty} to array store {self.spec.name!r} ({mode})."
        )
        logger.info(msg)

    def load(self, **identity: Any) -> "xr.DataArray":
        """Load one identity's array and coordinates as an :class:`xarray.DataArray`.

        Reads the identity's ``.npy`` blob (its shape and element dtype come from the file) and
        its coordinate row, then assembles a labelled array whose dimension order is the declared
        axis order. Positional (unlabelled) dimensions are left without coordinates.

        Args:
            **identity: One value per partition key, keyed by key name.

        Returns:
            The identity's data as an :class:`xarray.DataArray` named after the store.

        Raises:
            ValueError: If the identity keys do not match the partition keys.
            KeyError: If the store holds no array for this identity.
            ImportError: If xarray is not installed (it ships with the ``datastore`` extra).
        """
        try:
            import xarray as xr
        except ImportError as error:
            msg = (
                "ArrayStore.load() requires xarray; install the datastore extra "
                "(exporgo[datastore])."
            )
            raise ImportError(msg) from error
        self._validate_identity(identity)
        relative = self._fragment_path(identity)
        if relative is None:
            pretty = _partition.dict_of_identity(self.spec.partition_keys, identity)
            msg = (
                f"Array store {self.spec.name!r} holds no array for identity {pretty}."
            )
            raise KeyError(msg)
        with (self.root / relative).open("rb") as handle:
            array = np.load(handle)
        coord_values = self._read_coords(identity)
        coords = {
            dim: coord_values[dim]
            for dim in self.spec.labelled_dims
            if dim in coord_values
        }
        return xr.DataArray(
            array, dims=list(self.spec.dim_names), coords=coords, name=self.spec.name
        )

    def manifest(self) -> Manifest:
        """Return the store's array-fragment manifest, aggregated from its append-only log.

        Returns:
            The aggregated :class:`~exporgo.datastore.manifest.Manifest` (empty before any
            write). A live fragment's partition is the identity it belongs to.
        """
        return Manifest.from_log_directory(self.root / _MANIFEST_DIR)

    def scan_coords(self) -> pl.LazyFrame:
        """Return a lazy view of the coordinate catalog for cross-identity queries.

        Returns:
            A :class:`polars.LazyFrame` over the coordinate catalog: the partition-key columns
            plus one list-valued column per labelled dimension, one row per identity.
        """
        return self._coords.scan()

    def path(self, **identity: Any) -> Path | None:
        """Return the on-disk path of an identity's array, or ``None`` if it has none.

        Args:
            **identity: One value per partition key, keyed by key name.

        Returns:
            The absolute path to the identity's ``.npy`` blob, or ``None`` when absent.
        """
        self._validate_identity(identity)
        relative = self._fragment_path(identity)
        return None if relative is None else self.root / relative

    def write_schema(self) -> None:
        """Persist the coordinate catalog's schema anchor (its partition and coord dtypes)."""
        self._coords.write_schema()

    def _validate_identity(self, identity: dict[str, Any]) -> None:
        """Reject an identity whose keys do not exactly match the partition keys."""
        provided = set(identity)
        expected = set(self.spec.partition_keys)
        missing = expected - provided
        if missing:
            msg = f"Missing identity keys for {self.spec.name!r}: {sorted(missing)}."
            raise ValueError(msg)
        extra = provided - expected
        if extra:
            msg = f"Unexpected identity keys for {self.spec.name!r}: {sorted(extra)}."
            raise ValueError(msg)

    def _validate_coords(self, coords: dict[str, Any], shape: tuple[int, ...]) -> None:
        """Reject coordinates that miss a labelled dim, name an unknown dim, or mis-size."""
        labelled = set(self.spec.labelled_dims)
        provided = set(coords)
        missing = labelled - provided
        if missing:
            msg = (
                f"Array store {self.spec.name!r} requires coordinates for "
                f"{sorted(missing)}."
            )
            raise ValueError(msg)
        extra = provided - labelled
        if extra:
            msg = (
                f"Unexpected coordinates for {self.spec.name!r}: {sorted(extra)}; "
                f"labelled dims are {list(self.spec.labelled_dims)}."
            )
            raise ValueError(msg)
        for dim, values in coords.items():
            vector = np.asarray(values)
            if vector.ndim != 1:
                msg = f"Coordinate {dim!r} must be 1-D, got a {vector.ndim}-D vector."
                raise ValueError(msg)
            axis = self.spec.dim_names.index(dim)
            if vector.shape[0] != shape[axis]:
                msg = (
                    f"Coordinate {dim!r} has length {vector.shape[0]}, expected "
                    f"{shape[axis]} to match axis {axis} of the array."
                )
                raise ValueError(msg)

    def _write_coords(self, identity: dict[str, Any], coords: dict[str, Any]) -> None:
        """Write (overwrite) one identity's coordinate row in the catalog."""
        if not self.spec.labelled_dims:
            return
        row: dict[str, list[Any]] = {
            key: [identity[key]] for key in self.spec.partition_keys
        }
        for dim in self.spec.labelled_dims:
            row[dim] = [np.asarray(coords[dim]).tolist()]
        self._coords.write(pl.DataFrame(row), mode="overwrite")

    def _read_coords(self, identity: dict[str, Any]) -> dict[str, Any]:
        """Read one identity's coordinate vectors from the catalog (empty if none).

        Reads the identity's own partition directory directly (rather than filtering the whole
        catalog), so only that identity's coordinate fragment is touched and partition-key types
        never enter a predicate.
        """
        if not self.spec.labelled_dims:
            return {}
        partition_directory = self._coords.root / _partition.subpath(
            self.spec.partition_keys, identity
        )
        fragments = sorted(partition_directory.glob("part-*.parquet"))
        if not fragments:
            return {}
        frame = pl.read_parquet(fragments)
        if frame.height == 0:
            return {}
        record = frame.row(0, named=True)
        return {
            dim: np.asarray(record[dim])
            for dim in self.spec.labelled_dims
            if record.get(dim) is not None
        }

    def _write_array(self, identity: dict[str, Any], array: np.ndarray) -> str:
        """Write one identity's array as a uniquely-named ``.npy`` blob, atomically."""
        directory = self.root / _partition.subpath(self.spec.partition_keys, identity)
        directory.mkdir(parents=True, exist_ok=True)
        name = f"{_DATA_PREFIX}{uuid4().hex}.npy"
        target = directory / name
        temporary = target.with_name(f"{name}.{uuid4().hex}.tmp")
        with temporary.open("wb") as handle:
            np.save(handle, array)
        temporary.replace(target)
        return target.relative_to(self.root).as_posix()

    def _existing_partitions(self) -> set[tuple[str, ...]]:
        """The partition-value tuples already present, from the array manifest."""
        return _partition.existing(
            self.spec.partition_keys, self.manifest().partitions()
        )

    def _fragment_path(self, identity: dict[str, Any]) -> str | None:
        """Return the live fragment path for an identity, or ``None`` if absent."""
        keys = self.spec.partition_keys
        target = _partition.tuple_of_identity(keys, identity)
        found: str | None = None
        for fragment in self.manifest().fragments:
            if _partition.tuple_of_partition(keys, fragment.partition) == target:
                found = fragment.path
        return found

    def _remove_identity(self, target: tuple[str, ...]) -> None:
        """Delete an identity's array file(s) and tombstone them in the manifest log."""
        keys = self.spec.partition_keys
        removed: list[str] = []
        for fragment in self.manifest().fragments:
            if _partition.tuple_of_partition(keys, fragment.partition) == target:
                (self.root / fragment.path).unlink(missing_ok=True)
                removed.append(fragment.path)
        if removed:
            append_manifest_log(self.root / _MANIFEST_DIR, removed=removed)
