"""Shared fixtures for the logging tests.

Provides a fake loguru logger that records every interaction (so sink and decorator
configuration can be asserted without touching real sinks), and a factory for the
minimal record dicts loguru filters receive.
"""

from types import SimpleNamespace

import pytest


class RecordingLogger:
    """A stand-in for loguru's ``logger`` that records calls instead of acting."""

    def __init__(self) -> None:
        self.enabled: list[str] = []
        self.remove_calls: int = 0
        self.sinks: list[tuple[object, dict[str, object]]] = []
        self.entries: list[tuple[object, tuple[object, ...]]] = []
        self.opt_depths: list[int] = []

    def enable(self, name: str) -> None:
        self.enabled.append(name)

    def remove(self) -> None:
        self.remove_calls += 1

    def add(self, sink: object, **kwargs: object) -> int:
        self.sinks.append((sink, kwargs))
        return len(self.sinks)

    def opt(self, *, depth: int) -> "RecordingLogger":
        self.opt_depths.append(depth)
        return self

    def log(self, level: object, message: str, *args: object) -> None:
        self.entries.append((level, (message, *args)))


@pytest.fixture
def recording_logger() -> RecordingLogger:
    return RecordingLogger()


@pytest.fixture
def make_record():
    def _make_record(level: int, *, exception: object | None = None) -> dict[str, object]:
        return {"level": SimpleNamespace(no=int(level)), "exception": exception}

    return _make_record
