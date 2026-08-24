"""Study & Identity model — exporgo's shared foundation.

Declares a study's identity coordinate system (:class:`IdentitySchema` /
:class:`IdentityKey`) and its concrete addresses (:class:`Identity`). The monitoring
and datastore layers both build on this: identity keys become datastore partition
keys, and the study's validation seeds monitoring's derived status.
"""

from .identity import Identity, IdentityKey, IdentitySchema
from .resources import Resource
from .study import Study, ValidationReport

__all__ = [
    "Identity",
    "IdentityKey",
    "IdentitySchema",
    "Resource",
    "Study",
    "ValidationReport",
]
