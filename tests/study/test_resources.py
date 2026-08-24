"""Tests for Resource: named files/folders located by per-resource templates."""

from pathlib import Path

import pytest

from exporgo.study.identity import IdentityKey, IdentitySchema
from exporgo.study.resources import Resource

SCHEMA = IdentitySchema(keys=["Subject", IdentityKey(name="Session", dtype="int")])


def test_resource_exposes_its_template_placeholders() -> None:
    resource = Resource(name="suite2p", template="{Subject}/{Session}/suite2p/F.npy")
    assert resource.placeholders == ("Subject", "Session")


def test_resource_with_no_placeholders_is_constant() -> None:
    resource = Resource(name="atlas", template="shared/atlas.nii")
    assert resource.placeholders == ()


def test_resource_resolves_against_root_and_identity() -> None:
    identity = SCHEMA.identity(Subject="m01", Session=1)
    resource = Resource(name="suite2p", template="{Subject}/{Session}/suite2p/F.npy")

    resolved = resource.resolve(Path("D:/data/fomo"), identity)

    assert resolved == Path("D:/data/fomo/m01/1/suite2p/F.npy")


def test_resource_may_use_a_subset_of_identity_keys() -> None:
    identity = SCHEMA.identity(Subject="m01", Session=1)
    resource = Resource(name="genotype", template="{Subject}/genotype.txt")  # no Session

    assert resource.resolve(Path("D:/data"), identity) == Path("D:/data/m01/genotype.txt")


def test_resource_rejects_a_placeholder_absent_from_the_identity() -> None:
    identity = IdentitySchema.default().identity(Subject="m01")  # only Subject
    resource = Resource(name="x", template="{Subject}/{Session}/f")

    with pytest.raises(ValueError, match="Session"):
        resource.resolve(Path("D:/data"), identity)
