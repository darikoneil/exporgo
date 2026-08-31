"""Atomic file writes: publish a fresh file via a unique temporary plus a rename.

Writing to a uniquely-named temporary in the same directory and then renaming it onto the
target makes the write atomic on a single filesystem: a reader never sees a half-written file,
and concurrent writers resolve to last-writer-wins rather than a torn result. The unique
temporary name means two writers publishing the same target never collide on the scratch file.
Used for the small metadata files exporgo maintains (``study.toml``, filemap/dump sidecars, the
store schema anchor and manifest log).
"""

from pathlib import Path
from uuid import uuid4


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically (unique temp in the same directory, then rename).

    Args:
        path: The destination file.
        data: The bytes to write.
    """
    destination = Path(path)
    temporary = destination.with_name(f"{destination.name}.{uuid4().hex}.tmp")
    temporary.write_bytes(data)
    temporary.replace(destination)


def atomic_write_text(path: str | Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write ``text`` to ``path`` atomically (see :func:`atomic_write_bytes`).

    Args:
        path: The destination file.
        text: The text to write.
        encoding: The text encoding.
    """
    atomic_write_bytes(path, text.encode(encoding))
