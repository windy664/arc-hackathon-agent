import base64
from pathlib import Path

import pytest

MINI_REQUIREMENTS = """id: ROOT
name: Mini App
type: FOLDER
description: A tiny application for pipeline tests.
children:
- id: REQ-1
  name: Home Area
  type: FOLDER
  description: The home area.
  children:
  - id: REQ-1-1
    name: Landing Page
    type: ATOMIC
    description: |
      Users land on the home page. A button with the accessible name "New blank
      workbook" opens the creation form. The worksheet grid uses the ARIA grid
      role and cells expose aria-selected.

      Page reference:
      ![image](reference/home.png)
    scenarios:
    - name: REQ-1-1 open home
      steps:
      - keyword: GIVEN
        content: The seeded workbook `Q3 Sales` exists.
      - keyword: WHEN
        content: The user opens the home page.
      - keyword: THEN
        content: The workbook list shows `Q3 Sales`.
"""

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture
def mini_task(tmp_path: Path) -> Path:
    root = tmp_path / "mini-task"
    (root / "reference").mkdir(parents=True)
    (root / "requirements.yaml").write_text(MINI_REQUIREMENTS, encoding="utf-8")
    (root / "reference" / "home.png").write_bytes(TINY_PNG)
    return root


@pytest.fixture
def real_tasks_root() -> Path:
    return Path("/home/windy/下载/arcbench-hackathon-requirements")
