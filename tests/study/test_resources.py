"""Tests for ResourceSpec (declaration) and Resource (root-bound handle)."""

from pathlib import Path

import pytest

from exporgo.study.identity import Identity, IdentityKey, IdentitySchema
from exporgo.study.resources import (
    Resource,
    ResourceSpec,
    _template_to_glob,
    _template_to_regex,
)

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


def test_template_to_glob_replaces_placeholders_with_stars() -> None:
    assert _template_to_glob("{Subject}/{Session}/behavior.csv") == "*/*/behavior.csv"


def test_template_to_glob_handles_embedded_placeholders() -> None:
    assert _template_to_glob("{Subject}_raw.tif") == "*_raw.tif"


def test_template_to_regex_captures_named_segments() -> None:
    pattern = _template_to_regex("{Subject}/{Session}/behavior.csv")

    match = pattern.fullmatch("m01/1/behavior.csv")

    assert match is not None
    assert match.group("Subject") == "m01"
    assert match.group("Session") == "1"


def test_template_to_regex_confines_a_value_to_one_path_segment() -> None:
    pattern = _template_to_regex("{Subject}/behavior.csv")

    assert pattern.fullmatch("m01/extra/behavior.csv") is None


def test_template_to_regex_backreferences_repeated_placeholders() -> None:
    pattern = _template_to_regex("{Subject}/{Subject}_info.txt")

    assert pattern.fullmatch("m01/m01_info.txt") is not None
    assert pattern.fullmatch("m01/m02_info.txt") is None


def test_discover_finds_full_key_identities(tmp_path: Path) -> None:
    spec = ResourceSpec(name="beh", template="{Subject}/{Session}/behavior.csv")
    handle = Resource(tmp_path, spec, SCHEMA)
    for subject, session in [("m01", 1), ("m02", 2)]:
        directory = tmp_path / subject / str(session)
        directory.mkdir(parents=True)
        (directory / "behavior.csv").write_text("x", encoding="utf-8")

    assert handle.discover() == {
        SCHEMA.identity(Subject="m01", Session=1),
        SCHEMA.identity(Subject="m02", Session=2),
    }


def test_discover_returns_partial_identities_for_a_subset_template(
    tmp_path: Path,
) -> None:
    spec = ResourceSpec(name="geno", template="{Subject}/genotype.txt")  # no Session
    handle = Resource(tmp_path, spec, SCHEMA)
    (tmp_path / "m01").mkdir()
    (tmp_path / "m01" / "genotype.txt").write_text("x", encoding="utf-8")

    assert handle.discover() == {Identity(keys=("Subject",), values=("m01",))}


def test_discover_ignores_non_matching_files(tmp_path: Path) -> None:
    spec = ResourceSpec(name="beh", template="{Subject}/behavior.csv")
    handle = Resource(tmp_path, spec, IdentitySchema.default())
    (tmp_path / "m01").mkdir()
    (tmp_path / "m01" / "behavior.csv").write_text("x", encoding="utf-8")
    (tmp_path / "m02").mkdir()
    (tmp_path / "m02" / "other.csv").write_text("x", encoding="utf-8")  # no match

    assert handle.discover() == {Identity(keys=("Subject",), values=("m01",))}


def test_discover_of_a_constant_template_is_empty(tmp_path: Path) -> None:
    spec = ResourceSpec(name="atlas", template="shared/atlas.nii")
    handle = Resource(tmp_path, spec, IdentitySchema.default())
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "atlas.nii").write_text("x", encoding="utf-8")

    assert handle.discover() == set()


def test_discover_matches_folder_resources(tmp_path: Path) -> None:
    spec = ResourceSpec(name="suite2p", template="{Subject}/suite2p")
    handle = Resource(tmp_path, spec, IdentitySchema.default())
    (tmp_path / "m01" / "suite2p").mkdir(parents=True)  # a directory, not a file

    assert handle.discover() == {Identity(keys=("Subject",), values=("m01",))}


def test_discover_rejects_paths_breaking_a_repeated_placeholder(tmp_path: Path) -> None:
    spec = ResourceSpec(name="info", template="{Subject}/{Subject}_info.txt")
    handle = Resource(tmp_path, spec, IdentitySchema.default())
    (tmp_path / "m01").mkdir()
    (tmp_path / "m01" / "m01_info.txt").write_text("x", encoding="utf-8")  # backref holds
    (tmp_path / "m02").mkdir()
    (tmp_path / "m02" / "m03_info.txt").write_text("x", encoding="utf-8")  # backref fails

    assert handle.discover() == {Identity(keys=("Subject",), values=("m01",))}
