from pathlib import Path

from compiler.report import Reporter, ancestors


def test_ancestors() -> None:
    assert ancestors("REQ-1-1-1") == ["REQ-1-1-1", "REQ-1-1", "REQ-1", "ROOT"]
    assert ancestors("REQ-2") == ["REQ-2", "ROOT"]
    assert ancestors("ROOT") == ["ROOT"]


def test_reporter_never_raises(tmp_path: Path) -> None:
    r = Reporter(tmp_path)
    r.run_started("x")
    r.design_done(["REQ-1-1"], "y")
    r.implement_started(["REQ-1-1"], "z")
    r.implement_done(["REQ-1-1"], "z")
    r.interface("REQ-1-1.UI.Home", ["REQ-1-1"], "home", "frontend/src/pages/Home.tsx")
    r.test_passed(["REQ-1-1"], "ok")
    r.test_failed(["REQ-1-2"], "bad")
    r.run_completed("done")


def test_reporter_writes_events_when_sdk_available(tmp_path: Path) -> None:
    r = Reporter(tmp_path)
    if r.rt is None:
        return
    r.run_started("hello")
    events = tmp_path / ".arc" / "runner-events.jsonl"
    if not events.is_file():
        import os

        path = os.environ.get("ARCBENCH_RUNNER_EVENTS_PATH")
        if path:
            events = Path(path)
    assert events.is_file(), "expected runner events to be written"
    content = events.read_text(encoding="utf-8")
    assert "runner_state" in content
