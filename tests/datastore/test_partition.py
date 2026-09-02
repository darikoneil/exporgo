"""Tests for the shared Hive partition-path helpers used by both store kinds."""

from pathlib import Path

from exporgo.datastore import _partition

KEYS = ("Subject", "Session")


def test_subpath_renders_hive_key_value_segments() -> None:
    assert _partition.subpath(KEYS, {"Subject": "m01", "Session": 1}) == "Subject=m01/Session=1"


def test_dict_of_identity_stringifies_values_in_key_order() -> None:
    assert _partition.dict_of_identity(KEYS, {"Subject": "m01", "Session": 2}) == {
        "Subject": "m01",
        "Session": "2",
    }


def test_tuple_of_identity_stringifies_values_in_key_order() -> None:
    assert _partition.tuple_of_identity(KEYS, {"Session": 3, "Subject": "m01"}) == (
        "m01",
        "3",
    )


def test_tuple_of_partition_orders_by_keys_with_blanks_for_absent() -> None:
    assert _partition.tuple_of_partition(KEYS, {"Subject": "m01"}) == ("m01", "")


def test_from_path_parses_hive_segments_ignoring_the_filename() -> None:
    relative = Path("Subject=m01") / "Session=1" / "part-abc.parquet"
    assert _partition.from_path(relative) == {"Subject": "m01", "Session": "1"}


def test_from_path_ignores_non_hive_segments() -> None:
    assert _partition.from_path(Path("nothive") / "part.parquet") == {}


def test_existing_collects_partition_tuples_from_manifest_partitions() -> None:
    partitions = [
        {"Subject": "m01", "Session": "1"},
        {"Subject": "m02", "Session": "2"},
    ]
    assert _partition.existing(KEYS, partitions) == {("m01", "1"), ("m02", "2")}


def test_identity_and_partition_render_to_the_same_tuple() -> None:
    # An identity, its on-disk directory, and its manifest partition must all compare equal.
    identity = {"Subject": "m01", "Session": 1}
    from_identity = _partition.tuple_of_identity(KEYS, identity)
    from_manifest = _partition.tuple_of_partition(
        KEYS, _partition.from_path(Path(_partition.subpath(KEYS, identity)) / "x.parquet")
    )
    assert from_identity == from_manifest == ("m01", "1")
