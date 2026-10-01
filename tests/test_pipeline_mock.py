import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_mock_end_to_end(mini_task: Path, tmp_path: Path) -> None:
    out = tmp_path / "workspace"
    env = dict(os.environ)
    env["ARCBENCH_MOCK_MODEL"] = "1"
    env["ARCBENCH_MAX_SECONDS"] = "25"  # keeps visual stage (needs 240s+) out of unit tests
    env["ARCBENCH_MAX_MODEL_REQUESTS"] = "20"
    proc = subprocess.run(
        [sys.executable, "main.py", str(mini_task), "--output-dir", str(out)],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    # platform contract: frontend/ and backend/ at output root
    assert (out / "frontend" / "package.json").is_file()
    assert (out / "backend" / "package.json").is_file()

    backend_src = (out / "backend" / "src" / "index.js").read_text(encoding="utf-8")
    assert "process.env.PORT" in backend_src
    assert "frontend/dist" in backend_src.replace("\\", "/")

    pkg = json.loads((out / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert pkg["scripts"]["build"] == "vite build"

    assert (out / "frontend" / "vite.config.js").is_file()
    assert (out / "frontend" / "index.html").is_file()
    assert (out / "frontend" / "src" / "main.tsx").is_file()
    assert (out / "frontend" / "src" / "App.tsx").is_file()
    assert (out / "frontend" / "src" / "pages").is_dir()

    app_tsx = (out / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "Routes" in app_tsx
    assert "PAGES" in app_tsx
    pages = list((out / "frontend" / "src" / "pages").glob("*.tsx"))
    assert pages, "expected at least one generated page"
