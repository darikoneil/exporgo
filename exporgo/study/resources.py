"""Resources and dumps: the files a study reads but does not own.

Two components sit here. They differ in how many paths each one answers for, and in how
it learns them.

A :class:`ResourceSpec` declares a kind of data on disk (``"raw"``, ``"suite2p"``,
``"behavior"``) and carries a path template over the identity keys (using any subset of
them). A :class:`Resource` binds such a spec to a study root and identity schema so
callers can resolve concrete paths and check their existence for given identity values --
one *derived* path per identity, a file or a folder.

A :class:`Dump` instead *records* many paths: one study-global root and the files under it,
keyed by each file's path relative to that root (``atlas/annotation.nrrd``), for assets that
belong to the whole study rather than to any one identity -- an atlas, a README, a shared
lookup table. Nothing is copied or created on disk; the index persists to a sidecar JSON in
the dump's own directory. Files are looked up by an exact relative-path key or a glob: any
selector containing ``*`` is treated as an :mod:`fnmatch` pattern (where ``*`` crosses ``/``,
so ``"*annotation*"`` finds the file anywhere in the tree).

The resource pair mirrors the datastore's split of
:class:`~exporgo.datastore.spec.StoreSpec` (the declaration) and
:class:`~exporgo.datastore.store.Store` (the root-bound handle): ``ResourceSpec`` is to
``StoreSpec`` as ``Resource`` is to ``Store``. A dump has no such split -- its declaration is
just its name.
"""

import fnmatch
import re
from collections.abc import Mapping
from pathlib import Path
from string import Formatter
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from exporgo._atomic import atomic_write_text
from exporgo.study.identity import Identity, IdentitySchema, IdentityValue

__all__ = ["Dump", "Resource", "ResourceSpec"]

_DUMP_NAME = "_dump.json"


def _template_to_glob(template: str) -> str:
    """Turn a resource template into a filesystem glob (each ``{Key}`` becomes ``*``).

    Example:
        ``"{Subject}/{Session}/behavior.csv"`` -> ``"*/*/behavior.csv"``. The resulting
        glob over-matches (any string, across siblings); a regex from
        :func:`_template_to_regex` filters the candidates precisely.

    Args:
        template: A resource path template using ``{Key}`` placeholders.

    Returns:
        A glob pattern (relative to the resource root) matching the template's literals.
    """
    parts: list[str] = []
    for literal, field, _spec, _conversion in Formatter().parse(template):
        parts.append(literal)
        if field is not None:
            parts.append("*")
    return "".join(parts)


def _template_to_regex(template: str) -> re.Pattern[str]:
    """Compile a resource template into an anchored regex with one group per placeholder.

    Each literal is escaped verbatim and each ``{Key}`` becomes a named group
    ``(?P<Key>[^/]+)`` on first use, or a backreference ``(?P=Key)`` when the key repeats
    (so all occurrences of a key must resolve to the same value). ``[^/]+`` keeps a
    captured value within a single path segment. Match against a resource-root-relative
    **posix** path with :meth:`re.Pattern.fullmatch`.

    Args:
        template: A resource path template using ``{Key}`` placeholders.

    Returns:
        The compiled pattern; each placeholder's captured value is available by key name.
    """
    parts: list[str] = []
    seen: set[str] = set()
    for literal, field, _spec, _conversion in Formatter().parse(template):
        parts.append(re.escape(literal))
        if field is None:
            continue
        if field in seen:
            parts.append(f"(?P={field})")
        else:
            seen.add(field)
            parts.append(f"(?P<{field}>[^/]+)")
    return re.compile("".join(parts))


class ResourceSpec(BaseModel):
    """A named file/folder expected at each identity, located by a path template.

    The template uses ``{KeyName}`` placeholders drawn from the study's identity keys
    (any subset), e.g. ``"{Subject}/{Session}/suite2p/plane0/F.npy"``. A template with
    no placeholders resolves to the same path for every identity. This is the resource
    *declaration*; bind it to a study root with :class:`Resource` to resolve paths.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: str
    template: str

    @property
    def placeholders(self) -> tuple[str, ...]:
        """The identity key names referenced by this resource's template, in order."""
        fields = [
            field
            for _, field, _, _ in Formatter().parse(self.template)
            if field is not None
        ]
        return tuple(dict.fromkeys(fields))

    def resolve(self, root: Path, identity: Identity) -> Path:
        """Resolve this resource to a concrete path under ``root`` for ``identity``.

        Args:
            root: The study root directory.
            identity: The identity supplying values for the template placeholders.

        Returns:
            The resolved path (``root`` joined with the filled-in template).

        Raises:
            ValueError: If the template references a key the identity does not provide.
        """
        mapping = identity.to_dict()
        missing = [name for name in self.placeholders if name not in mapping]
        if missing:
            msg = (
                f"Resource {self.name!r} template references identity keys "
                f"not present in {identity!r}: {missing}"
            )
            raise ValueError(msg)
        relative = self.template.format(**mapping)
        return root.joinpath(relative)


class Resource:
    """A resource declaration bound to a study root and identity schema.

    Pairs a :class:`ResourceSpec` with the study root and identity schema needed to turn
    identity values into concrete paths, so it is the resource counterpart of the
    datastore's :class:`~exporgo.datastore.store.Store`. Obtain one via
    :meth:`~exporgo.study.study.Study.resource`; the study supplies the root and schema.
    """

    def __init__(
        self,
        root: str | Path,
        spec: ResourceSpec,
        schema: IdentitySchema,
    ) -> None:
        """Bind a resource spec to a study root and identity schema.

        Args:
            root: The study root directory the template resolves against.
            spec: The resource declaration (name + path template).
            schema: The study's identity schema, used to validate and coerce the identity
                values passed to :meth:`path` / :meth:`exists`.
        """
        self.root: Path = Path(root)
        self.spec = spec
        self.schema = schema

    def path(self, **values: IdentityValue) -> Path:
        """Resolve this resource's on-disk path for the given identity values.

        Args:
            **values: One value per identity key, keyed by key name (e.g.
                ``Subject="m01", Session=1``); each is coerced to its key's dtype.

        Returns:
            The resolved path under the study root, returned whether or not it exists.

        Raises:
            ValueError: If a key is missing or an unexpected key is supplied.
        """
        return self.spec.resolve(self.root, self.schema.identity(**values))

    def exists(self, **values: IdentityValue) -> bool:
        """Whether this resource's resolved path exists for the given identity values.

        Args:
            **values: One value per identity key, keyed by key name.

        Returns:
            ``True`` if the resolved path exists on disk, otherwise ``False``.

        Raises:
            ValueError: If a key is missing or an unexpected key is supplied.
        """
        return self.path(**values).exists()

    def discover(self) -> set[Identity]:
        """Reverse-resolve the template to find which identities exist on disk.

        The inverse of :meth:`path`: scans the study root for paths matching the template
        and reads each placeholder's value back out, yielding an open-world inventory of
        what is physically present (including unregistered identities). A subset-key
        template yields **partial** identities; a constant template yields an empty set.
        Captured segments are coerced to their key's dtype via the schema.

        Returns:
            The identities physically present on disk, one per matching path (files and
            folders both match). Empty when the template has no placeholders or the root
            has no matches.

        Note:
            Cost is one directory glob plus a regex match per candidate path; nothing is
            read from the files themselves.
        """
        placeholders = self.spec.placeholders
        if not placeholders:
            return set()
        pattern = _template_to_regex(self.spec.template)
        key_by_name = {key.name: key for key in self.schema.keys}
        found: set[Identity] = set()
        for candidate in self.root.glob(_template_to_glob(self.spec.template)):
            relative = candidate.relative_to(self.root).as_posix()
            match = pattern.fullmatch(relative)
            if match is None:
                continue
            values = tuple(
                key_by_name[name].coerce(match.group(name)) for name in placeholders
            )
            found.add(Identity(keys=placeholders, values=values))
        return found

    @property
    def name(self) -> str:
        """The resource's name."""
        return self.spec.name

    @property
    def template(self) -> str:
        """The resource's path template."""
        return self.spec.template

    @property
    def placeholders(self) -> tuple[str, ...]:
        """The identity key names referenced by the template, in order."""
        return self.spec.placeholders


def _index_directory(
    directory: Path, *, pattern: str, recursive: bool, ignore: str
) -> dict[str, str]:
    """Index the files under ``directory``, keyed by their posix path relative to it.

    Args:
        directory: The folder to scan (the dump's root).
        pattern: Glob selecting which files to include (``"*"`` for all).
        recursive: Whether to descend into subdirectories.
        ignore: A filename to exclude, e.g. the component's own sidecar -- relevant when
            ``directory`` is (or contains) the component's own directory.

    Returns:
        A ``{relative_key -> absolute_path}`` mapping, e.g.
        ``{"atlas/annotation.nrrd": "/refs/atlas/annotation.nrrd"}``. Relative keys are
        unique within a tree, so no two files collide.

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
        if item.is_file() and item.name != ignore
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


class _DumpDocument(BaseModel):
    """The persisted content of a dump: a study-global root and its relative-path-keyed files."""

    root: str | None = None
    files: dict[str, str] = Field(default_factory=dict)


class Dump:
    """A study-global index of files, keyed by path relative to a single root.

    Where a :class:`Resource` derives one path per identity, a dump records many paths that
    belong to no identity at all: one root and one relative-path-keyed file set for the whole
    study, for assets that are shared rather than per-subject (an atlas, a README, a shared
    lookup table). Obtain one via :meth:`~exporgo.study.study.Study.dump`.
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
        self,
        directory: str | Path | None = None,
        *,
        pattern: str = "*",
        recursive: bool = True,
    ) -> dict[str, Path]:
        """Index ``directory``, keying each file by its posix path relative to it.

        Replaces the dump's recorded files with the folder's current contents.

        Args:
            directory: The folder to index (the dump's root). Defaults to the dump's own
                directory (``<study_root>/<name>``).
            pattern: Glob selecting which files to index (``"*"`` for all).
            recursive: Whether to descend into subdirectories.

        Returns:
            The ``{relative_key -> Path}`` files indexed by this scan.

        Raises:
            NotADirectoryError: If ``directory`` is not an existing directory.
        """
        root = Path(directory) if directory is not None else self.directory
        found = _index_directory(
            root, pattern=pattern, recursive=recursive, ignore=_DUMP_NAME
        )
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
