"""FileMap and Dump: recorded indexes of file locations, keyed by relative path.

A :class:`FileMap` is the study component for files exporgo *reads* but does not own and
cannot derive from a single template -- raw acquisitions, processing-tool outputs like
suite2p (``F.npy``, ``Fneu.npy``, ...), temporary intermediates. Each identity maps to a
**root** folder and the files under it, keyed by their **path relative to that root**
(``plane0/F.npy``), so same-named files in different subfolders never collide.

A filemap has one of two modes, fixed at declaration:

- **templated** -- a ``root_template`` over the identity keys derives each identity's root
  folder (e.g. ``"{Subject}/{Session}/suite2p"``); :meth:`FileMap.discover` walks it with no
  path passed.
- **recorded** -- you supply each identity's root (the folder handed to
  :meth:`FileMap.discover`) or pin loose files with :meth:`FileMap.record`.

A :class:`Dump` is the same index without the identity dimension -- one study-global root for
assets that belong to the whole study (an atlas, a README, a shared lookup table).

Files are looked up by an exact relative-path key or a glob: any selector containing ``*`` is
treated as an :mod:`fnmatch` pattern (where ``*`` crosses ``/``, so ``"*iscell*"`` finds the
file anywhere in the tree). Records persist to a sidecar JSON in the component's directory;
nothing is copied or created on disk.
"""

import fnmatch
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, Field

from exporgo._atomic import atomic_write_text
from exporgo.study.identity import Identity, IdentitySchema, IdentityValue
from exporgo.study.resources import ResourceSpec

__all__ = ["Dump", "FileMap"]

_FILEMAP_NAME = "_filemap.json"
_DUMP_NAME = "_dump.json"


def _index_directory(
    directory: Path, *, pattern: str, recursive: bool
) -> dict[str, str]:
    """Index the files under ``directory``, keyed by their posix path relative to it.

    Args:
        directory: The folder to scan (the identity's root).
        pattern: Glob selecting which files to include (``"*"`` for all).
        recursive: Whether to descend into subdirectories.

    Returns:
        A ``{relative_key -> absolute_path}`` mapping, e.g.
        ``{"plane0/F.npy": "/data/m01/suite2p/plane0/F.npy"}``. Relative keys are unique
        within a tree, so no two files collide.

    Raises:
        NotADirectoryError: If ``directory`` is not an existing directory.
    """
    if not directory.is_dir():
        msg = f"Cannot discover files: {directory} is not a directory."
        raise NotADirectoryError(msg)
    globber = directory.rglob if recursive else directory.glob
    return {
        item.relative_to(directory).as_posix(): str(item)
        for item in sorted(globber(pattern))
        if item.is_file()
    }


def _matching(files: Mapping[str, str], selector: str) -> dict[str, Path]:
    """Return the ``{key -> Path}`` entries matching ``selector``.

    A selector containing ``*`` is an :func:`fnmatch.fnmatchcase` glob (``*`` crosses ``/``);
    otherwise it is an exact key lookup.

    Args:
        files: The recorded ``{key -> path}`` mapping to search.
        selector: An exact relative-path key or a glob pattern.

    Returns:
        The matching entries as ``{key -> Path}`` (empty if none match).
    """
    if "*" in selector:
        return {
            key: Path(value)
            for key, value in files.items()
            if fnmatch.fnmatchcase(key, selector)
        }
    if selector in files:
        return {selector: Path(files[selector])}
    return {}


def _one(files: Mapping[str, str], selector: str, *, where: str) -> Path:
    """Resolve ``selector`` to exactly one file.

    Args:
        files: The recorded ``{key -> path}`` mapping to search.
        selector: An exact relative-path key or a glob pattern.
        where: A short description of the component, for error messages.

    Returns:
        The single matching :class:`~pathlib.Path`.

    Raises:
        KeyError: If nothing matches ``selector``.
        ValueError: If ``selector`` (a glob) matches more than one file.
    """
    matches = _matching(files, selector)
    if not matches:
        msg = f"No file matching {selector!r} in {where}; keys: {sorted(files)}"
        raise KeyError(msg)
    if len(matches) > 1:
        msg = f"{selector!r} is ambiguous in {where}; it matched {sorted(matches)}"
        raise ValueError(msg)
    return next(iter(matches.values()))


def _all_present(files: Mapping[str, str]) -> bool:
    """True when at least one file is recorded and every recorded file exists on disk."""
    return bool(files) and all(Path(value).exists() for value in files.values())


class _FileMapEntry(BaseModel):
    """One identity's record: its identity, its root, and its relative-path-keyed files."""

    identity: dict[str, str]
    root: str | None = None
    files: dict[str, str] = Field(default_factory=dict)


class _FileMapDocument(BaseModel):
    """The persisted content of a filemap: one entry per recorded identity."""

    entries: list[_FileMapEntry] = Field(default_factory=list)


class FileMap:
    """A recorded index of files per identity, keyed by path relative to the identity's root.

    Obtain one via :meth:`~exporgo.study.study.Study.filemap`. The mode is fixed at
    construction: pass ``root_template`` for a **templated** filemap (each identity's root is
    derived from the template), or omit it for a **recorded** filemap (you supply the root to
    :meth:`discover`, or pin loose files with :meth:`record`).
    """

    def __init__(
        self,
        study_root: str | Path,
        name: str,
        schema: IdentitySchema,
        *,
        root_template: str | None = None,
    ) -> None:
        """Bind a filemap to the study root, its name, the identity schema, and its mode.

        Args:
            study_root: The study's root directory. The sidecar lives in
                ``<study_root>/<name>/``; a templated ``root_template`` resolves against this
                root.
            name: The filemap's name.
            schema: The study's identity schema, used to validate and coerce identity values.
            root_template: A path template over the identity keys locating each identity's root
                folder (e.g. ``"{Subject}/{Session}/suite2p"``). ``None`` makes the filemap
                *recorded* rather than *templated*.
        """
        self.study_root = Path(study_root)
        self.name = name
        self.schema = schema
        self.root_template = root_template
        self._template_spec = (
            ResourceSpec(name=name, template=root_template)
            if root_template is not None
            else None
        )

    @property
    def templated(self) -> bool:
        """Whether this filemap derives each identity's root from a template."""
        return self.root_template is not None

    @property
    def directory(self) -> Path:
        """The filemap's own directory (``<study_root>/<name>``), where the sidecar lives."""
        return self.study_root / self.name

    @property
    def sidecar(self) -> Path:
        """The path to this filemap's persisted sidecar JSON."""
        return self.directory / _FILEMAP_NAME

    def _load(self) -> _FileMapDocument:
        """Read the sidecar document (an empty document if it does not exist)."""
        if not self.sidecar.exists():
            return _FileMapDocument()
        return _FileMapDocument.model_validate_json(
            self.sidecar.read_text(encoding="utf-8")
        )

    def _save(self, document: _FileMapDocument) -> None:
        """Persist the sidecar document, creating the filemap directory if needed."""
        self.directory.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.sidecar, document.model_dump_json(indent=2))

    @staticmethod
    def _identity_key(identity: Identity) -> dict[str, str]:
        """String-encode an identity's ``{key: value}`` mapping for storage and lookup."""
        return {key: str(value) for key, value in identity.to_dict().items()}

    def _entry(
        self, document: _FileMapDocument, identity: Identity
    ) -> _FileMapEntry | None:
        """Return the document entry for ``identity`` (``None`` if it has none)."""
        target = self._identity_key(identity)
        return next(
            (entry for entry in document.entries if entry.identity == target), None
        )

    def _files(self, identity: Identity) -> dict[str, str]:
        """Return the recorded ``{key -> path}`` for ``identity`` (empty if none)."""
        entry = self._entry(self._load(), identity)
        return dict(entry.files) if entry is not None else {}

    def _discover_root(self, identity: Identity, directory: str | Path | None) -> Path:
        """Determine the root to index for ``identity`` from the mode and ``directory``.

        Templated filemaps derive the root and reject an explicit ``directory``; recorded
        filemaps take the passed ``directory`` (or reuse a root stored by a prior discover).

        Raises:
            ValueError: If a templated filemap is given a ``directory``, or a recorded filemap
                is given none and has no stored root yet.
        """
        if self._template_spec is not None:
            if directory is not None:
                msg = (
                    f"Filemap {self.name!r} is templated; it derives each identity's root, "
                    "so don't pass a directory to discover()."
                )
                raise ValueError(msg)
            return self._template_spec.resolve(self.study_root, identity)
        if directory is not None:
            return Path(directory)
        entry = self._entry(self._load(), identity)
        if entry is None or entry.root is None:
            msg = (
                f"Recorded filemap {self.name!r} has no root for {identity!r} yet; "
                "pass a directory to discover() the first time."
            )
            raise ValueError(msg)
        return Path(entry.root)

    def discover(
        self,
        directory: str | Path | None = None,
        *,
        pattern: str = "*",
        recursive: bool = True,
        **values: IdentityValue,
    ) -> dict[str, Path]:
        """Index an identity's root folder, keying each file by its path relative to the root.

        Replaces (reconciles) the identity's recorded files with the folder's current
        contents, so re-running picks up new files and drops vanished ones. In **templated**
        mode the root is derived from the template (pass no ``directory``); in **recorded**
        mode the ``directory`` you pass becomes the identity's root.

        Args:
            directory: The folder to index (recorded mode). Omit it for a templated filemap,
                or to re-index a recorded identity's previously stored root.
            pattern: Glob selecting which files to index (``"*"`` for all).
            recursive: Whether to descend into subdirectories.
            **values: One value per identity key.

        Returns:
            The ``{relative_key -> Path}`` files indexed by this scan.

        Raises:
            ValueError: If a key is missing/unexpected, a templated filemap is given a
                ``directory``, or a recorded filemap is given none with no stored root.
            NotADirectoryError: If the resolved root is not an existing directory.
        """
        identity = self.schema.identity(**values)
        root = self._discover_root(identity, directory)
        found = _index_directory(root, pattern=pattern, recursive=recursive)
        document = self._load()
        entry = self._entry(document, identity)
        if entry is None:
            entry = _FileMapEntry(identity=self._identity_key(identity))
            document.entries.append(entry)
        entry.root = str(root)
        entry.files = found
        self._save(document)
        return {key: Path(value) for key, value in found.items()}

    def record(
        self,
        path: str | Path,
        *,
        name: str | None = None,
        **values: IdentityValue,
    ) -> Path:
        """Pin a single file location for an identity under an explicit key.

        For loose files that don't share a common root (recorded mode). The file is stored
        as-given (typically absolute), is not required to exist, and is never copied.

        Args:
            path: The file's location.
            name: The key to record it under; defaults to the file's name (with suffix).
            **values: One value per identity key.

        Returns:
            The recorded location as a :class:`~pathlib.Path`.

        Raises:
            ValueError: If a key is missing or an unexpected key is supplied.
        """
        identity = self.schema.identity(**values)
        resolved = Path(path)
        key = name if name is not None else resolved.name
        document = self._load()
        entry = self._entry(document, identity)
        if entry is None:
            entry = _FileMapEntry(identity=self._identity_key(identity))
            document.entries.append(entry)
        entry.files[key] = str(resolved)
        self._save(document)
        return resolved

    def paths(
        self, pattern: str | None = None, **values: IdentityValue
    ) -> dict[str, Path]:
        """Return the recorded files for an identity, all or matching a glob.

        Args:
            pattern: An :mod:`fnmatch` glob over the relative-path keys, or ``None`` for all.
            **values: One value per identity key.

        Returns:
            The matching files as ``{key -> Path}`` (empty if none).

        Raises:
            ValueError: If a key is missing or an unexpected key is supplied.
        """
        identity = self.schema.identity(**values)
        files = self._files(identity)
        if pattern is None:
            return {key: Path(value) for key, value in files.items()}
        return _matching(files, pattern)

    def path(self, selector: str, **values: IdentityValue) -> Path:
        """Return the single recorded file matching ``selector`` for an identity.

        Args:
            selector: An exact relative-path key, or a glob if it contains ``*`` (which must
                match exactly one file).
            **values: One value per identity key.

        Returns:
            The matching location as a :class:`~pathlib.Path`.

        Raises:
            KeyError: If nothing matches ``selector`` for the identity.
            ValueError: If a key is missing/unexpected, or ``selector`` is an ambiguous glob.
        """
        identity = self.schema.identity(**values)
        files = self._files(identity)
        return _one(files, selector, where=f"filemap {self.name!r} for {values}")

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
        identity = self.schema.identity(**values)
        return _all_present(self._files(identity))

    def identities(self) -> set[Identity]:
        """Return the identities that have at least one recorded file."""
        document = self._load()
        return {self.schema.identity(**entry.identity) for entry in document.entries}


class _DumpDocument(BaseModel):
    """The persisted content of a dump: a study-global root and its relative-path-keyed files."""

    root: str | None = None
    files: dict[str, str] = Field(default_factory=dict)


class Dump:
    """A study-global index of files, keyed by path relative to a single root.

    A :class:`FileMap` without the identity dimension: one root and one relative-path-keyed
    file set for the whole study, for assets that aren't per-identity (an atlas, a README, a
    shared lookup table). Obtain one via :meth:`~exporgo.study.study.Study.dump`.
    """

    def __init__(self, directory: str | Path, name: str) -> None:
        """Bind a dump to its directory and name.

        Args:
            directory: The dump's directory (``<study_root>/<name>``); its sidecar
                ``_dump.json`` lives here.
            name: The dump's name.
        """
        self.directory = Path(directory)
        self.name = name

    @property
    def sidecar(self) -> Path:
        """The path to this dump's persisted sidecar JSON."""
        return self.directory / _DUMP_NAME

    def _load(self) -> _DumpDocument:
        """Read the sidecar document (an empty document if it does not exist)."""
        if not self.sidecar.exists():
            return _DumpDocument()
        return _DumpDocument.model_validate_json(
            self.sidecar.read_text(encoding="utf-8")
        )

    def _save(self, document: _DumpDocument) -> None:
        """Persist the sidecar document, creating the dump directory if needed."""
        self.directory.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.sidecar, document.model_dump_json(indent=2))

    def discover(
        self, directory: str | Path, *, pattern: str = "*", recursive: bool = True
    ) -> dict[str, Path]:
        """Index ``directory``, keying each file by its posix path relative to it.

        Replaces the dump's recorded files with the folder's current contents.

        Args:
            directory: The folder to index (the dump's root).
            pattern: Glob selecting which files to index (``"*"`` for all).
            recursive: Whether to descend into subdirectories.

        Returns:
            The ``{relative_key -> Path}`` files indexed by this scan.

        Raises:
            NotADirectoryError: If ``directory`` is not an existing directory.
        """
        root = Path(directory)
        found = _index_directory(root, pattern=pattern, recursive=recursive)
        self._save(_DumpDocument(root=str(root), files=found))
        return {key: Path(value) for key, value in found.items()}

    def record(self, path: str | Path, *, name: str | None = None) -> Path:
        """Pin a single study-global file under an explicit key.

        Args:
            path: The file's location (stored as-given; not required to exist; never copied).
            name: The key to record it under; defaults to the file's name (with suffix).

        Returns:
            The recorded location as a :class:`~pathlib.Path`.
        """
        resolved = Path(path)
        key = name if name is not None else resolved.name
        document = self._load()
        document.files[key] = str(resolved)
        self._save(document)
        return resolved

    def paths(self, pattern: str | None = None) -> dict[str, Path]:
        """Return the recorded files, all or matching a glob.

        Args:
            pattern: An :mod:`fnmatch` glob over the relative-path keys, or ``None`` for all.

        Returns:
            The matching files as ``{key -> Path}`` (empty if none).
        """
        files = self._load().files
        if pattern is None:
            return {key: Path(value) for key, value in files.items()}
        return _matching(files, pattern)

    def path(self, selector: str) -> Path:
        """Return the single recorded file matching ``selector``.

        Args:
            selector: An exact relative-path key, or a glob if it contains ``*`` (which must
                match exactly one file).

        Returns:
            The matching location as a :class:`~pathlib.Path`.

        Raises:
            KeyError: If nothing matches ``selector``.
            ValueError: If ``selector`` is an ambiguous glob.
        """
        return _one(self._load().files, selector, where=f"dump {self.name!r}")

    def exists(self) -> bool:
        """Whether the dump has recorded files and all of them exist on disk."""
        return _all_present(self._load().files)
