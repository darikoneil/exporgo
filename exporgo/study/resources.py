"""Resources: named files/folders a study expects, located by path templates.

A :class:`ResourceSpec` declares a kind of data on disk (``"raw"``, ``"suite2p"``,
``"behavior"``) and carries a path template over the identity keys (using any subset of
them). A :class:`Resource` binds such a spec to a study root and identity schema so
callers can resolve concrete paths and check their existence for given identity values.

The pair mirrors the datastore's split of
:class:`~exporgo.datastore.spec.StoreSpec` (the declaration) and
:class:`~exporgo.datastore.store.Store` (the root-bound handle): ``ResourceSpec`` is to
``StoreSpec`` as ``Resource`` is to ``Store``.
"""

import re
from pathlib import Path
from string import Formatter
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from exporgo.study.identity import Identity, IdentitySchema, IdentityValue

__all__ = ["Resource", "ResourceSpec"]


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
