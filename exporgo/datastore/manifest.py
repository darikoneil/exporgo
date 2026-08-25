"""Per-store manifest: the inventory of fragments written to a datastore component.

The manifest is a small JSON index that answers "what's in this store?" (which
partitions, which fragment files, how many rows) without scanning the Parquet data. It
is the basis for fast existence checks and, later, overwrite-by-key and schema versioning.
"""

from pydantic import BaseModel, Field

__all__ = ["FragmentEntry", "Manifest"]


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


class Manifest(BaseModel):
    """A datastore component's inventory of written fragments.

    Attributes:
        schema_version: Version of the manifest layout, for forward migration.
        fragments: The written fragments, in write order.
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
        """Return the total number of rows across all fragments."""
        return sum(fragment.rows for fragment in self.fragments)
