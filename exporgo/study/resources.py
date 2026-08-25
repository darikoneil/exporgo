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

from pathlib import Path
from string import Formatter
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from exporgo.study.identity import Identity, IdentitySchema, IdentityValue

__all__ = ["Resource", "ResourceSpec"]


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
        self.root = Path(root)
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
