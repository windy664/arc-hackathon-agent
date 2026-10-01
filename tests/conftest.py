from pathlib import Path

import pytest

from tests.fixture_data import write_fixture


@pytest.fixture
def mini_task(tmp_path: Path) -> Path:
    return write_fixture(tmp_path / "mini-task")


@pytest.fixture
def real_tasks_root() -> Path:
    return Path("/home/windy/下载/arcbench-hackathon-requirements")
