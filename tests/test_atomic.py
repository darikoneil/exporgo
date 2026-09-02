"""Tests for the atomic write-then-rename primitive underpinning safe metadata writes."""

from pathlib import Path

from exporgo._atomic import atomic_write_bytes, atomic_write_text


def test_write_bytes_round_trips(tmp_path: Path) -> None:
    target = tmp_path / "data.bin"
    atomic_write_bytes(target, b"\x00\x01\x02payload")
    assert target.read_bytes() == b"\x00\x01\x02payload"


def test_write_text_round_trips(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    atomic_write_text(target, '{"name": "study"}')
    assert target.read_text(encoding="utf-8") == '{"name": "study"}'


def test_write_overwrites_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    atomic_write_text(target, "old")
    atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_no_scratch_file_survives(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    atomic_write_text(target, "content")
    # The unique ``.tmp`` scratch file is renamed onto the target, never left behind.
    assert [entry.name for entry in tmp_path.iterdir()] == ["config.json"]


def test_honors_encoding(tmp_path: Path) -> None:
    target = tmp_path / "text.dat"
    atomic_write_text(target, "café", encoding="utf-16")
    assert target.read_text(encoding="utf-16") == "café"
    assert target.read_bytes() == "café".encode("utf-16")


def test_concurrent_writers_to_distinct_targets_are_isolated(tmp_path: Path) -> None:
    # The real concurrency pattern: writers publish to their own unique paths (as the
    # manifest and per-writer logs do). Each write is atomic and the uuid-tagged scratch
    # files never collide, so every target lands with its own complete, untorn content.
    from concurrent.futures import ThreadPoolExecutor

    def write(index: int) -> None:
        atomic_write_text(tmp_path / f"writer-{index}.txt", f"payload-{index}" * 1000)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(8)))

    for index in range(8):
        target = tmp_path / f"writer-{index}.txt"
        assert target.read_text(encoding="utf-8") == f"payload-{index}" * 1000
    # No leftover ``.tmp`` scratch files from any writer.
    assert sorted(entry.name for entry in tmp_path.iterdir()) == [
        f"writer-{index}.txt" for index in range(8)
    ]
