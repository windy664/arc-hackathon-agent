"""Write the mini task fixture used by the CI scaffold job."""

from pathlib import Path

from tests.conftest import MINI_REQUIREMENTS, TINY_PNG


def main() -> None:
    root = Path("ci-mini-task")
    (root / "reference").mkdir(parents=True, exist_ok=True)
    (root / "requirements.yaml").write_text(MINI_REQUIREMENTS, encoding="utf-8")
    (root / "reference" / "home.png").write_bytes(TINY_PNG)
    print(f"fixture written to {root.resolve()}")


if __name__ == "__main__":
    main()
