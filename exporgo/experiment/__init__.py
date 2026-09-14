"""Experiment & Identity model — exporgo's shared foundation.

Declares an experiment's identity coordinate system (:class:`IdentitySchema` /
:class:`IdentityKey`) and its concrete addresses (:class:`Identity`). The monitoring
and datastore layers both build on this: identity keys become datastore partition
keys, and the experiment's validation seeds monitoring's derived status.
"""

from exporgo.experiment.experiment import CoverageReport, Experiment, ValidationReport
from exporgo.experiment.identity import Identity, IdentityKey, IdentitySchema
from exporgo.experiment.resources import Dump, Resource, ResourceSpec

__all__ = [
    "CoverageReport",
    "Dump",
    "Experiment",
    "Identity",
    "IdentityKey",
    "IdentitySchema",
    "Resource",
    "ResourceSpec",
    "ValidationReport",
]
