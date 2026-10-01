"""Write the mini task fixture used by the CI scaffold job."""

from pathlib import Path

from tests.fixture_data import write_fixture


def main() -> None:
    root = write_fixture(Path("ci-mini-task"))
    print(f"fixture written to {root.resolve()}")


if __name__ == "__main__":
    main()
