"""Per-store manifest: an append-only log of the fragments written to a component.

The manifest answers "what's in this store?" (which partitions, which fragment files, how
many rows) without scanning the Parquet data. It is stored as an **append-only log directory**
``<store>/_manifest/``: each write drops its own uniquely-named ``<uuid>.json`` entry recording
the fragments it added (and, for overwrite-by-key, the fragments it tombstoned). Nothing is
ever read-modify-written, so independent writers -- even on separate machines sharing the store
over a network filesystem -- never clobber each other's entries. A read aggregates the whole
directory (applying tombstones) into a single :class:`Manifest`. This mirrors the data files,
which already avoid collisions via unique ``part-<uuid>.parquet`` names; the manifest is the
matching commit log.
"""

from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from exporgo._atomic import atomic_write_text

__all__ = ["FragmentEntry", "Manifest"]

_LOG_GLOB = "*.json"


class FragmentEntry(BaseModel):
    """One written Parquet fragment: its path, partition, row count, and timestamp.

    Attributes:
        path: The fragment's path relative to the store root, POSIX-style.
        partition: The fragment's Hive partition as a ``{key: value}`` mapping.
        rows: The number of rows in the fragment.
        written: The write time as an ISO-8601 UTC timestamp.
    """

    path: str
    partition: dict[str, str]
    rows: int
    written: str


class _ManifestLog(BaseModel):
    """One write's contribution to the append-only manifest log.

    Attributes:
        added: Fragments this write created.
        removed: Fragment paths this write tombstoned (overwrite-by-key deletes).
    """

    added: list[FragmentEntry] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)


class Manifest(BaseModel):
    """A datastore component's inventory of live fragments, aggregated from the log.

    Built by :meth:`from_log_directory`, which reads every log entry and drops any fragment a
    later entry tombstoned. Purely in-memory; the on-disk source of truth is the append-only
    ``_manifest/`` directory.

    Attributes:
        schema_version: Version of the manifest layout, for forward migration.
        fragments: The live fragments, in write order.
    """

    schema_version: int = 1
    fragments: list[FragmentEntry] = Field(default_factory=list)

    def partitions(self) -> list[dict[str, str]]:
        """Return the distinct partition key-combos present, in first-seen order."""
        seen: list[dict[str, str]] = []
        for fragment in self.fragments:
            if fragment.partition not in seen:
                seen.append(fragment.partition)
        return seen

    def row_count(self) -> int:
        """Return the total number of rows across all live fragments."""
        return sum(fragment.rows for fragment in self.fragments)

    @classmethod
    def from_log_directory(cls, directory: Path) -> "Manifest":
        """Aggregate an append-only manifest log directory into a single manifest.

        Reads every ``<uuid>.json`` log entry in ``directory``, concatenates the fragments they
        added, and drops any fragment whose path a later entry tombstoned. Live fragments are
        ordered by their write timestamp.

        Args:
            directory: The store's ``_manifest/`` log directory.

        Returns:
            The aggregated :class:`Manifest` (empty if the directory does not exist).
        """
        if not directory.is_dir():
            return cls()
        added: list[FragmentEntry] = []
        removed: set[str] = set()
        for path in sorted(directory.glob(_LOG_GLOB)):
            log = _ManifestLog.model_validate_json(path.read_text(encoding="utf-8"))
            added.extend(log.added)
            removed.update(log.removed)
        live = sorted(
            (entry for entry in added if entry.path not in removed),
            key=lambda entry: entry.written,
        )
        return cls(fragments=live)


def append_manifest_log(
    directory: Path,
    *,
    added: list[FragmentEntry] | None = None,
    removed: list[str] | None = None,
) -> None:
    """Append one write's fragments and tombstones as a unique log entry.

    Writes a fresh ``<uuid>.json`` under ``directory``, published atomically (written to a
    temporary name, then renamed), so a reader never sees a half-written entry and no two
    writers ever contend for the same file.

    Args:
        directory: The store's ``_manifest/`` log directory (created if absent).
        added: Fragments created by this write.
        removed: Fragment paths tombstoned by this write (overwrite-by-key).
    """
    directory.mkdir(parents=True, exist_ok=True)
    log = _ManifestLog(added=added or [], removed=removed or [])
    atomic_write_text(directory / f"{uuid4().hex}.json", log.model_dump_json(indent=2))
