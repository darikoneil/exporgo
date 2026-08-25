"""Tests for ResourceSpec (declaration) and Resource (root-bound handle)."""

from pathlib import Path

import pytest

from exporgo.study.identity import IdentityKey, IdentitySchema
from exporgo.study.resources import Resource, ResourceSpec

SCHEMA = IdentitySchema(keys=["Subject", IdentityKey(name="Session", dtype="int")])


def test_spec_exposes_its_template_placeholders() -> None:
    spec = ResourceSpec(name="suite2p", template="{Subject}/{Session}/suite2p/F.npy")
    assert spec.placeholders == ("Subject", "Session")


def test_spec_with_no_placeholders_is_constant() -> None:
    spec = ResourceSpec(name="atlas", template="shared/atlas.nii")
    assert spec.placeholders == ()


def test_spec_resolves_against_root_and_identity() -> None:
    identity = SCHEMA.identity(Subject="m01", Session=1)
    spec = ResourceSpec(name="suite2p", template="{Subject}/{Session}/suite2p/F.npy")

    resolved = spec.resolve(Path("D:/data/fomo"), identity)

    assert resolved == Path("D:/data/fomo/m01/1/suite2p/F.npy")


def test_spec_may_use_a_subset_of_identity_keys() -> None:
    identity = SCHEMA.identity(Subject="m01", Session=1)
    spec = ResourceSpec(name="genotype", template="{Subject}/genotype.txt")  # no Session

    assert spec.resolve(Path("D:/data"), identity) == Path("D:/data/m01/genotype.txt")


def test_spec_rejects_a_placeholder_absent_from_the_identity() -> None:
    identity = IdentitySchema.default().identity(Subject="m01")  # only Subject
    spec = ResourceSpec(name="x", template="{Subject}/{Session}/f")

    with pytest.raises(ValueError, match="Session"):
        spec.resolve(Path("D:/data"), identity)


def test_handle_path_resolves_for_identity_values() -> None:
    spec = ResourceSpec(name="suite2p", template="{Subject}/{Session}/F.npy")
    handle = Resource(Path("D:/data/fomo"), spec, SCHEMA)

    assert handle.path(Subject="m01", Session=1) == Path("D:/data/fomo/m01/1/F.npy")


def test_handle_exists_reflects_the_filesystem(tmp_path: Path) -> None:
    spec = ResourceSpec(name="beh", template="{Subject}/behavior.csv")
    handle = Resource(tmp_path, spec, IdentitySchema.default())

    assert not handle.exists(Subject="m01")
    (tmp_path / "m01").mkdir()
    (tmp_path / "m01" / "behavior.csv").write_text("x", encoding="utf-8")
    assert handle.exists(Subject="m01")


def test_handle_exposes_passthrough_properties() -> None:
    spec = ResourceSpec(name="suite2p", template="{Subject}/{Session}/F.npy")
    handle = Resource(Path("D:/data"), spec, SCHEMA)

    assert handle.name == "suite2p"
    assert handle.template == "{Subject}/{Session}/F.npy"
    assert handle.placeholders == ("Subject", "Session")
