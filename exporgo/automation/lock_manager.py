"""
Lock Manager Stub
"""
from ..tools import convert
from ..types import File


class LockManager:
    locked_files = set()
    _running = False

    @classmethod
    @convert(parameter="file", permitted=(File, ), required=str)
    def request_lock(cls, file: File) -> bool:
        if file in cls.locked_files:
            return False
        cls.locked_files.add(file)
        return True

    @classmethod
    @convert(parameter="file", permitted=(File, ), required=str)
    def release_lock(cls, file: File) -> None:
        cls.locked_files.remove(file)

    @classmethod
    def idle(cls) -> bool:
        return len(cls.locked_files) == 0

    @classmethod
    def is_running(cls) -> bool:
        return cls._running

    @classmethod
    def start(cls) -> None:
        cls._running = True

    @classmethod
    def stop(cls) -> None:
        if cls.is_running() and len(cls.locked_files) == 0:
            cls._running = False
        else:
            raise RuntimeError("Cannot stop LockManager while files are locked.")
