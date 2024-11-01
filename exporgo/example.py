from exporgo.subject import Subject
from pathlib import Path


def green_beans(s: Path) -> None:
    subject = Subject.load(s)
    print(f"{subject.name} is a green bean!")
