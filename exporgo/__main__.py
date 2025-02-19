import argparse
from pathlib import Path

from .automation.manager import ExporgoManager
from .types import File

# TODO: Finish implementing the main function


def execute_exporgo(file: File) -> None:
    with ExporgoManager(file) as manager:
        print(f"ENTERED {file}")
        for experiment_key, experiment in manager.subject.experiments.items():
            print(experiment_key, experiment)  # temporary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute Exporgo with the specified file."
    )
    parser.add_argument(
        "file", type=str, help="The path to the subject's organization file."
    )

    args = parser.parse_args()
    file = Path(args.file)

    execute_exporgo(file)


if __name__ == "__main__":
    main()
