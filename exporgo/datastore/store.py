"""A single datastore component: schema-enforced partitioned writes and lazy scans."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import polars as pl
import pyarrow.dataset as ds
from loguru import logger

from exporgo.datastore import _partition
from exporgo.datastore.manifest import FragmentEntry, Manifest, append_manifest_log
from exporgo.datastore.spec import StoreSpec

__all__ = ["Store"]

_MANIFEST_DIR = "_manifest"
_SCHEMA_NAME = "_schema.parquet"


class Store:
    """One datastore component: a Hive-partitioned Parquet dataset governed by a spec.

    ``write`` validates and casts a frame to the declared schema, then writes it
    partitioned by the spec's keys. ``scan`` returns a lazy, partition-prunable
    :class:`polars.LazyFrame` with the declared schema restored.
    """

    def __init__(self, root: str | Path, spec: StoreSpec) -> None:
        """Bind a store to its root directory and specification.

        Args:
            root: The directory holding this component's Parquet dataset.
            spec: The store's declared schema, partition keys, and sort column.
        """
        self.root = Path(root)
        self.spec = spec

    def _validate_columns(self, frame: pl.DataFrame) -> None:
        """Reject a frame whose columns do not exactly match the declared schema."""
        provided = set(frame.columns)
        expected = set(self.spec.column_names)
        missing = expected - provided
        if missing:
            msg = f"Missing columns for store {self.spec.name!r}: {sorted(missing)}"
            raise ValueError(msg)
        extra = provided - expected
        if extra:
            msg = f"Unexpected columns for store {self.spec.name!r}: {sorted(extra)}"
            raise ValueError(msg)

    def write(
        self,
        frame: pl.DataFrame,
        *,
        mode: Literal["append", "overwrite", "unique"] = "append",
    ) -> None:
        """Validate, cast, and write ``frame`` -- appending, overwriting, or unique-only.

        Modes:

        - ``"append"`` (default): each write adds new fragments (a partition may gain
          more rows across writes).
        - ``"overwrite"``: the partitions present in ``frame`` are **replaced** -- their
          existing fragments (files + manifest entries) are deleted before the new data
          is written; partitions absent from ``frame`` are left untouched.
        - ``"unique"``: refuse the write if ``frame`` carries any identity (partition) the
          store already contains -- nothing is written (all-or-nothing).

        All modes are out-of-core -- data for other partitions is never read.

        Args:
            frame: The data to write; its columns must match the declared schema.
            mode: ``"append"`` to add, ``"overwrite"`` to replace by partition,
                ``"unique"`` to add only if no incoming identity is already present.

        Raises:
            ValueError: If the frame's columns do not match the declared schema, or if
                ``mode="unique"`` and an incoming identity is already in the store.

        Note:
            See the "Write to a store" how-to for choosing among the modes.
        """
        self._validate_columns(frame)
        frame = frame.cast(self.spec.polars_schema())
        if self.spec.sort_column is not None:
            frame = frame.sort(self.spec.sort_column)
        self.root.mkdir(parents=True, exist_ok=True)
        if mode == "overwrite":
            self._remove_partitions(self._incoming_partitions(frame))
        elif mode == "unique":
            self._reject_existing_partitions(frame)
        written: list[Any] = []
        ds.write_dataset(
            frame.to_arrow(),
            base_dir=str(self.root),
            format="parquet",
            partitioning=list(self.spec.partition_keys),
            partitioning_flavor="hive",
            existing_data_behavior="overwrite_or_ignore",
            basename_template=f"part-{uuid4().hex}-{{i}}.parquet",
            file_visitor=written.append,
            use_threads=True,
            max_rows_per_file=self.spec.max_rows_per_file,
            max_rows_per_group=self.spec.max_rows_per_group,
        )
        timestamp = datetime.now(UTC).isoformat()
        self._record_fragments(
            [self._fragment_entry(written_file, timestamp) for written_file in written]
        )
        msg = (
            f"Wrote {frame.height} rows to store {self.spec.name!r} "
            f"({mode}, {len(written)} fragment(s))."
        )
        logger.info(msg)

    def scan(self) -> pl.LazyFrame:
        """Return a lazy, partition-prunable view with the declared schema restored.

        Nothing is read from disk until the frame is collected; filters on the partition
        keys push down to skip whole files and row groups.

        Returns:
            A :class:`polars.LazyFrame` over the component's Parquet fragments, cast to
            the declared schema and projected to the declared columns.

        Note:
            Chain ``.filter(...)`` on the partition keys *before* ``.collect()`` to keep
            partition pruning; collecting first materializes the whole dataset.
        """
        lazy = pl.scan_parquet(
            self.root / "**" / "part-*.parquet", hive_partitioning=True
        )
        return lazy.cast(self.spec.polars_schema()).select(self.spec.column_names)

    def manifest(self) -> Manifest:
        """Return the store's fragment manifest, aggregated from its append-only log.

        Reads every entry in the ``_manifest/`` log directory and applies tombstones (see
        :meth:`~exporgo.datastore.manifest.Manifest.from_log_directory`). Empty when the store
        has no data yet.

        Returns:
            The aggregated :class:`~exporgo.datastore.manifest.Manifest`.
        """
        return Manifest.from_log_directory(self.root / _MANIFEST_DIR)

    @property
    def schema(self) -> pl.Schema:
        """The store's declared column schema (name -> polars dtype).

        The in-memory schema from the store's
        :class:`~exporgo.datastore.spec.StoreSpec` -- the same schema
        :meth:`write_schema` persists and :meth:`scan` restores. Cheap (no IO) and
        available even before anything has been written. Use the static
        :meth:`read_schema` only when no store instance exists (the bootstrap during
        :meth:`~exporgo.study.study.Study.load`).

        Returns:
            The declared schema as a :class:`polars.Schema` (a dict-like mapping).
        """
        return self.spec.polars_schema()

    def write_schema(self) -> None:
        """Persist the store's declared schema as a 0-row anchor Parquet file, atomically."""
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / _SCHEMA_NAME
        temporary = target.with_name(f"{_SCHEMA_NAME}.{uuid4().hex}.tmp")
        pl.DataFrame(schema=self.spec.polars_schema()).write_parquet(temporary)
        temporary.replace(target)

    @staticmethod
    def read_schema(root: str | Path) -> dict[str, Any]:
        """Read a store's persisted column schema (name -> dtype) from its anchor.

        Reads the 0-row anchor Parquet written by :meth:`write_schema`, letting a study
        reload a store's schema without re-declaring its columns in code. This is the
        pre-instance bootstrap (before a :class:`Store`/``StoreSpec`` exists); with a live
        store in hand, use the :attr:`schema` property instead (in-memory, no IO).

        Args:
            root: The store's root directory (holding ``_schema.parquet``).

        Returns:
            The column schema as a ``{name: polars dtype}`` mapping.
        """
        schema = pl.scan_parquet(Path(root) / _SCHEMA_NAME).collect_schema()
        return dict(schema)

    def _record_fragments(self, entries: list[FragmentEntry]) -> None:
        """Record one write's fragments as a new append-only manifest log entry."""
        if entries:
            append_manifest_log(self.root / _MANIFEST_DIR, added=entries)

    def _fragment_entry(self, written_file: Any, timestamp: str) -> FragmentEntry:
        """Build a manifest entry from a pyarrow ``WrittenFile``."""
        raw = Path(written_file.path)
        try:
            relative = raw.relative_to(self.root)
        except ValueError:
            relative = raw
        return FragmentEntry(
            path=relative.as_posix(),
            partition=_partition.from_path(relative),
            rows=written_file.metadata.num_rows,
            written=timestamp,
        )

    def _incoming_partitions(self, frame: pl.DataFrame) -> set[tuple[str, ...]]:
        """Distinct partition-key tuples in ``frame``, path-encoded as strings."""
        keys = self.spec.partition_keys
        distinct = frame.select(list(keys)).unique()
        return {
            _partition.tuple_of_identity(keys, row)
            for row in distinct.iter_rows(named=True)
        }

    def _existing_partitions(self) -> set[tuple[str, ...]]:
        """The partition-key tuples already present in the store, from the manifest."""
        return _partition.existing(
            self.spec.partition_keys, self.manifest().partitions()
        )

    def _reject_existing_partitions(self, frame: pl.DataFrame) -> None:
        """Raise if ``frame`` carries any identity (partition) the store already contains."""
        conflicts = self._incoming_partitions(frame) & self._existing_partitions()
        if conflicts:
            keys = list(self.spec.partition_keys)
            pretty = [
                dict(zip(keys, values, strict=True)) for values in sorted(conflicts)
            ]
            msg = (
                f"Store {self.spec.name!r} already contains identities {pretty}; "
                f"refusing to write (mode='unique')."
            )
            raise ValueError(msg)

    def _remove_partitions(self, targets: set[tuple[str, ...]]) -> None:
        """Delete the target partitions' data files and tombstone them in the manifest log."""
        keys = self.spec.partition_keys
        removed: list[str] = []
        for fragment in self.manifest().fragments:
            if _partition.tuple_of_partition(keys, fragment.partition) in targets:
                (self.root / fragment.path).unlink(missing_ok=True)
                removed.append(fragment.path)
        if removed:
            append_manifest_log(self.root / _MANIFEST_DIR, removed=removed)
