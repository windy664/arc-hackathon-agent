import importlib
import os
from pathlib import Path


def test_parse_args_with_positional_and_output(tmp_path, monkeypatch):
    import main as entry

    importlib.reload(entry)
    src, out = entry.parse_args(["req-dir", "--output-dir", str(tmp_path / "o")])
    assert src == Path("req-dir")
    assert out == tmp_path / "o"


def test_parse_args_bare_uses_env(monkeypatch):
    import main as entry

    monkeypatch.setenv("ARCBENCH_TASK_DIR", "env-req")
    monkeypatch.setenv("ARCBENCH_OUTPUT_DIR", "env-out")
    importlib.reload(entry)
    src, out = entry.parse_args([])
    assert src == Path("env-req")
    assert out == Path("env-out")


def test_parse_args_type_flag_not_treated_as_source(monkeypatch):
    import main as entry

    monkeypatch.delenv("ARCBENCH_TASK_DIR", raising=False)
    monkeypatch.delenv("ARCBENCH_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("ARCBENCH_TEMPLATE_DIR", raising=False)
    importlib.reload(entry)
    src, out = entry.parse_args(["--type", "web"])
    assert src == Path("requirements")
    assert out == Path("/workspace/template")
    src2, _ = entry.parse_args(["tasks/x", "--type", "web"])
    assert src2 == Path("tasks/x")
