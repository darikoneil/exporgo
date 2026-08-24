"""Per-store manifest: the inventory of fragments written to a datastore component.

The manifest is a small JSON index that answers "what's in this store?" (which
partitions, which fragment files, how many rows) without scanning the Parquet data. It
is the basis for fast existence checks and, later, overwrite-by-key and schema versioning.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["FragmentEntry", "Manifest"]


class FragmentEntry(BaseModel):
    """One written Parquet fragment: its path, partition, row count, and timestamp."""

    path: str
    partition: dict[str, str]
    rows: int
    written: str


class Manifest(BaseModel):
    """A datastore component's inventory of written fragments."""

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
        """Return the total number of rows across all fragments."""
        return sum(fragment.rows for fragment in self.fragments)
