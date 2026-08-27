"""FileMap: a recorded index of external file locations per identity.

A :class:`FileMap` is the third study component type, alongside
:class:`~exporgo.study.resources.Resource` (templated locations) and
:class:`~exporgo.datastore.store.Store` (owned data). Where a resource *derives* a path
from a template, a filemap *records* the concrete location(s) of particular files for an
identity -- typically raw acquisition files that live anywhere on disk (an external drive)
and do not follow a naming pattern.

Each identity maps to a ``{name -> path}`` set (the name defaults to the file's stem,
mirroring the original exporgo's filemap). Recorded paths are stored as-given (absolute,
outside the study root); nothing is copied or created. The record persists to a sidecar
``_filemap.json`` in the filemap's directory and self-validates existence via
:meth:`FileMap.exists`. :meth:`FileMap.discover` populates it by indexing a directory.
"""

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, Field

from exporgo.study.identity import Identity, IdentitySchema, IdentityValue

__all__ = ["FileMap"]

_FILEMAP_NAME = "_filemap.json"


class _FileMapEntry(BaseModel):
    """One identity's recorded files: its identity and a ``{name -> path}`` map."""

    identity: dict[str, str]
    files: dict[str, str]


class _FileMapDocument(BaseModel):
    """The persisted content of a filemap: recorded file locations per identity."""

    entries: list[_FileMapEntry] = Field(default_factory=list)


class FileMap:
    """A recorded index of external file locations, keyed by identity.

    Records, per identity, a ``{name -> Path}`` map of concrete file locations (stored
    as-given, typically absolute and outside the study root), persisted to a sidecar
    ``_filemap.json``. The third study component type; obtain one via
    :meth:`~exporgo.study.study.Study.filemap`.
    """

    def __init__(self, root: str | Path, name: str, schema: IdentitySchema) -> None:
        """Bind a filemap to its directory, name, and the study identity schema.

        Args:
            root: The filemap's directory (``<study_root>/<name>``); its sidecar
                ``_filemap.json`` lives here.
            name: The filemap's name.
            schema: The study's identity schema, used to validate and coerce the identity
                values passed to the recording and lookup methods.
        """
        self.root = Path(root)
        self.name = name
        self.schema = schema

    @property
    def sidecar(self) -> Path:
        """The path to this filemap's persisted sidecar JSON."""
        return self.root / _FILEMAP_NAME

    def _load(self) -> _FileMapDocument:
        """Read the sidecar document (an empty document if it does not exist)."""
        if not self.sidecar.exists():
            return _FileMapDocument()
        return _FileMapDocument.model_validate_json(
            self.sidecar.read_text(encoding="utf-8")
        )

    def _save(self, document: _FileMapDocument) -> None:
        """Persist the sidecar document, creating the filemap directory if needed."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.sidecar.write_text(document.model_dump_json(indent=2), encoding="utf-8")

    @staticmethod
    def _identity_key(identity: Identity) -> dict[str, str]:
        """String-encode an identity's ``{key: value}`` mapping for storage and lookup."""
        return {key: str(value) for key, value in identity.to_dict().items()}

    def _write_files(self, identity: Identity, files: Mapping[str, str]) -> None:
        """Merge ``{name: path}`` into the identity's entry and persist the sidecar."""
        document = self._load()
        target = self._identity_key(identity)
        entry = next((e for e in document.entries if e.identity == target), None)
        if entry is None:
            entry = _FileMapEntry(identity=target, files={})
            document.entries.append(entry)
        entry.files.update(files)
        self._save(document)

    def record(
        self,
        path: str | Path,
        *,
        name: str | None = None,
        **values: IdentityValue,
    ) -> Path:
        """Record a file location for an identity.

        Args:
            path: The file's location (stored as-given, typically absolute and anywhere on
                disk); it is not required to exist yet and is never copied or created.
            name: The name to record it under; defaults to the file's stem.
            **values: One value per identity key.

        Returns:
            The recorded location as a :class:`~pathlib.Path`.

        Raises:
            ValueError: If a key is missing or an unexpected key is supplied.
        """
        identity = self.schema.identity(**values)
        resolved = Path(path)
        key = name if name is not None else resolved.stem
        self._write_files(identity, {key: str(resolved)})
        return resolved

    def paths(self, **values: IdentityValue) -> dict[str, Path]:
        """Return the ``{name -> Path}`` files recorded for an identity (empty if none).

        Args:
            **values: One value per identity key.

        Returns:
            The recorded files as a ``{name: Path}`` mapping.

        Raises:
            ValueError: If a key is missing or an unexpected key is supplied.
        """
        identity = self.schema.identity(**values)
        target = self._identity_key(identity)
        document = self._load()
        entry = next((e for e in document.entries if e.identity == target), None)
        if entry is None:
            return {}
        return {name: Path(location) for name, location in entry.files.items()}

    def path(self, name: str, **values: IdentityValue) -> Path:
        """Return the single recorded file ``name`` for an identity.

        Args:
            name: The recorded file's name.
            **values: One value per identity key.

        Returns:
            The recorded location as a :class:`~pathlib.Path`.

        Raises:
            KeyError: If no file with that name is recorded for the identity.
            ValueError: If a key is missing or an unexpected key is supplied.
        """
        files = self.paths(**values)
        try:
            return files[name]
        except KeyError:
            msg = (
                f"No file named {name!r} recorded for {values} in filemap "
                f"{self.name!r}; recorded names: {sorted(files)}"
            )
            raise KeyError(msg) from None

    def exists(self, **values: IdentityValue) -> bool:
        """Whether the identity has recorded files and all of them exist on disk.

        Args:
            **values: One value per identity key.

        Returns:
            ``True`` if at least one file is recorded for the identity and every recorded
            file exists, otherwise ``False``.

        Raises:
            ValueError: If a key is missing or an unexpected key is supplied.
        """
        files = self.paths(**values)
        return bool(files) and all(location.exists() for location in files.values())

    def identities(self) -> set[Identity]:
        """Return the identities that have at least one recorded file."""
        document = self._load()
        return {self.schema.identity(**entry.identity) for entry in document.entries}

    def discover(
        self,
        directory: str | Path,
        *,
        pattern: str = "*",
        recursive: bool = True,
        **values: IdentityValue,
    ) -> dict[str, Path]:
        """Index a directory and record every file found under an identity.

        Scans ``directory`` (recursively by default) and records each file by its stem,
        mirroring the original exporgo's directory indexing. Existing records for the same
        names are overwritten; on a stem collision within one scan the last match (in
        sorted path order) wins.

        Args:
            directory: The directory to scan (may be anywhere on disk).
            pattern: Glob pattern selecting which files to record.
            recursive: Whether to descend into subdirectories.
            **values: One value per identity key.

        Returns:
            The ``{name -> Path}`` files recorded by this scan.

        Raises:
            ValueError: If a key is missing or an unexpected key is supplied.
            NotADirectoryError: If ``directory`` is not an existing directory.
        """
        identity = self.schema.identity(**values)
        directory = Path(directory)
        if not directory.is_dir():
            msg = f"Cannot discover files: {directory} is not a directory."
            raise NotADirectoryError(msg)
        globber = directory.rglob if recursive else directory.glob
        found = {item.stem: item for item in sorted(globber(pattern)) if item.is_file()}
        self._write_files(identity, {name: str(item) for name, item in found.items()})
        return found
