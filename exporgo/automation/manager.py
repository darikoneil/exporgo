from time import sleep, time

from ..exceptions import FileLockError
from ..organization.subject import Subject
from ..types import File
from .lock_manager import LockManager


class ExporgoManager:

    timeout_duration = 60 * 15 # 15 minutes

    retry_interval = 30 # 30 seconds

    def __init__(self, file: File):

        #: subject's organization file
        self.file = file

        if not self.file.exists():
            raise FileNotFoundError(f"File {self.file} does not exist.")

        if not self.file_manager_running:
            self.start_file_manager()

    @property
    def file_manager_running(self):
        return LockManager.is_running()

    @staticmethod
    def start_file_manager() -> None:
        LockManager.start()

    @staticmethod
    def stop_file_manager() -> None:
        LockManager.stop()

    @staticmethod
    def load_subject(file: File) -> "Subject":
        return Subject.load(file)

    # noinspection PyUnusedLocal
    @staticmethod
    def request_lock(file: File) -> bool:
        return LockManager.request_lock(file)

    @staticmethod
    def release_lock(file: File) -> None:
        LockManager.release_lock(file)

    @classmethod
    def lock_file(cls, file: File) -> bool:
        start_time = time()
        while not (locked := cls.request_lock(file) and (time()) - start_time < cls.timeout_duration):
            sleep(cls.retry_interval)
        return locked

    def __enter__(self):
        if not self.lock_file(self.file):
            raise FileLockError(self.file)
        self.subject = self.load_subject(self.file)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.subject.index()
        self.subject.save()
        self.subject = None
        self.release_lock(self.file)
        if LockManager.idle():
            self.stop_file_manager()
