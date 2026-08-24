"""Resources: named files/folders a study expects, located by path templates.

A :class:`Resource` names a kind of data on disk (``"raw"``, ``"suite2p"``,
``"behavior"``) and carries a path template over the identity keys (using any subset
of them). Combined with an :class:`~exporgo.study.identity.Identity` and a study root,
it resolves to a concrete path -- which the study then checks for existence.
"""

from pathlib import Path
from string import Formatter
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from exporgo.study.identity import Identity

__all__ = ["Resource"]


class Resource(BaseModel):
    """A named file/folder expected at each identity, located by a path template.

    The template uses ``{KeyName}`` placeholders drawn from the study's identity keys
    (any subset), e.g. ``"{Subject}/{Session}/suite2p/plane0/F.npy"``. A template with
    no placeholders resolves to the same path for every identity.
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
