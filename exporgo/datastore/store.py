"""A single datastore component: schema-enforced partitioned writes and lazy scans."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import polars as pl
import pyarrow.dataset as ds

from .manifest import FragmentEntry, Manifest

if TYPE_CHECKING:
    from typing import Any, Literal

    from .spec import StoreSpec

__all__ = ["Store"]

_MANIFEST_NAME = "_manifest.json"
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
        mode: Literal["append", "overwrite"] = "append",
    ) -> None:
        """Validate, cast, and write ``frame`` -- appending, or overwriting by key.

        With ``mode="append"`` (default) each write adds new fragments. With
        ``mode="overwrite"`` the partitions present in ``frame`` are **replaced**:
        their existing fragments (files + manifest entries) are deleted before the new
        data is written; partitions absent from ``frame`` are left untouched. Both are
        out-of-core -- data for other partitions is never read.

        Args:
            frame: The data to write; its columns must match the declared schema.
            mode: ``"append"`` to add, ``"overwrite"`` to replace by partition.

        Raises:
            ValueError: If the frame's columns do not match the declared schema.
        """
        self._validate_columns(frame)
        frame = frame.cast(self.spec.polars_schema())
        if self.spec.sort_column is not None:
            frame = frame.sort(self.spec.sort_column)
        self.root.mkdir(parents=True, exist_ok=True)
        if mode == "overwrite":
            self._remove_partitions(self._incoming_partitions(frame))
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
        )
        timestamp = datetime.now(UTC).isoformat()
        self._record_fragments(
            [self._fragment_entry(written_file, timestamp) for written_file in written]
        )

    def scan(self) -> pl.LazyFrame:
        """Return a lazy, partition-prunable view with the declared schema restored."""
        lazy = pl.scan_parquet(
            self.root / "**" / "part-*.parquet", hive_partitioning=True
        )
        return lazy.cast(self.spec.polars_schema()).select(self.spec.column_names)

    def manifest(self) -> Manifest:
        """Return the store's fragment manifest (empty if nothing has been written)."""
        path = self.root / _MANIFEST_NAME
        if not path.exists():
            return Manifest()
        return Manifest.model_validate_json(path.read_text(encoding="utf-8"))

    def write_schema(self) -> None:
        """Persist the store's declared schema as a 0-row anchor Parquet file."""
        self.root.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(schema=self.spec.polars_schema()).write_parquet(
            self.root / _SCHEMA_NAME
        )

    @staticmethod
    def read_schema(root: str | Path) -> dict[str, Any]:
        """Read a store's persisted column schema (name -> dtype) from its anchor."""
        schema = pl.scan_parquet(Path(root) / _SCHEMA_NAME).collect_schema()
        return dict(schema)

    def _record_fragments(self, entries: list[FragmentEntry]) -> None:
        """Append fragment entries to the on-disk manifest."""
        current = self.manifest()
        updated = Manifest(
            schema_version=current.schema_version,
            fragments=[*current.fragments, *entries],
        )
        (self.root / _MANIFEST_NAME).write_text(
            updated.model_dump_json(indent=2), encoding="utf-8"
        )

    def _fragment_entry(self, written_file: Any, timestamp: str) -> FragmentEntry:
        """Build a manifest entry from a pyarrow ``WrittenFile``."""
        raw = Path(written_file.path)
        try:
            relative = raw.relative_to(self.root)
        except ValueError:
            relative = raw
        return FragmentEntry(
            path=relative.as_posix(),
            partition=self._partition_from_path(relative),
            rows=written_file.metadata.num_rows,
            written=timestamp,
        )

    @staticmethod
    def _partition_from_path(relative: Path) -> dict[str, str]:
        """Parse Hive ``key=value`` segments from a fragment's relative path."""
        partition: dict[str, str] = {}
        for segment in relative.parts[:-1]:
            key, separator, value = segment.partition("=")
            if separator:
                partition[key] = value
        return partition

    def _incoming_partitions(self, frame: pl.DataFrame) -> set[tuple[str, ...]]:
        """Distinct partition-key tuples in ``frame``, path-encoded as strings."""
        keys = list(self.spec.partition_keys)
        distinct = frame.select(keys).unique()
        return {
            tuple(str(row[key]) for key in keys)
            for row in distinct.iter_rows(named=True)
        }

    def _remove_partitions(self, targets: set[tuple[str, ...]]) -> None:
        """Delete fragments (files + manifest entries) for the target partitions."""
        manifest = self.manifest()
        kept: list[FragmentEntry] = []
        for fragment in manifest.fragments:
            if self._partition_tuple(fragment.partition) in targets:
                (self.root / fragment.path).unlink(missing_ok=True)
            else:
                kept.append(fragment)
        updated = Manifest(schema_version=manifest.schema_version, fragments=kept)
        (self.root / _MANIFEST_NAME).write_text(
            updated.model_dump_json(indent=2), encoding="utf-8"
        )

    def _partition_tuple(self, partition: dict[str, str]) -> tuple[str, ...]:
        """Order a fragment's partition dict by the spec's partition keys."""
        return tuple(partition.get(key, "") for key in self.spec.partition_keys)
