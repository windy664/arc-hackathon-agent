from pathlib import Path

from compiler.repair import map_problem_to_area, verify_sources
from compiler.requirements import (
    collect_atomics,
    derive_contract,
    find_reference_images,
    load_requirements,
)
from compiler.generate import plan_ui_areas


def _areas(mini_task: Path):
    data, req_dir = load_requirements(mini_task)
    atomics: list[dict] = []
    collect_atomics(data, [], atomics)
    images = find_reference_images(atomics, req_dir)
    return plan_ui_areas(atomics, images), atomics


def test_map_problem_by_requirement_id(mini_task: Path) -> None:
    areas, _ = _areas(mini_task)
    key = map_problem_to_area("REQ-1-1 visual diff: button wrong", areas, {})
    assert key == "home.png"


def test_map_problem_by_name_phrase(mini_task: Path) -> None:
    areas, _ = _areas(mini_task)
    key = map_problem_to_area("missing accessible name: New blank workbook", areas, {})
    assert key == "home.png"


def test_verify_sources_reports_missing_contract(mini_task: Path, tmp_path: Path) -> None:
    areas, atomics = _areas(mini_task)
    contract = derive_contract(atomics)
    out = tmp_path / "out"
    src = out / "frontend" / "src"
    src.mkdir(parents=True)
    (src / "Empty.tsx").write_text(
        "export default function Empty() {\n  return <div>nothing</div>\n}\n",
        encoding="utf-8",
    )
    problems = verify_sources(out, contract, areas, {"home.png": "Empty"})
    details = " ".join(p["detail"] for p in problems)
    assert "New blank workbook" in details
    assert "grid" in details


def test_verify_sources_clean_when_contract_met(mini_task: Path, tmp_path: Path) -> None:
    areas, atomics = _areas(mini_task)
    contract = derive_contract(atomics)
    out = tmp_path / "out"
    src = out / "frontend" / "src"
    src.mkdir(parents=True)
    (src / "Full.tsx").write_text(
        "export default function Full() {\n"
        "  return (\n"
        "    <div role=\"grid\" aria-selected=\"true\">\n"
        "      <button>New blank workbook</button>\n"
        "    </div>\n"
        "  )\n"
        "}\n",
        encoding="utf-8",
    )
    problems = verify_sources(out, contract, areas, {"home.png": "Full"})
    assert problems == []


def test_repair_area_uses_patch_script(mini_task: Path, tmp_path: Path, monkeypatch) -> None:
    import os

    from compiler.repair import repair_area

    monkeypatch.setenv("ARCBENCH_MOCK_MODEL", "1")
    from compiler import model as model_mod

    monkeypatch.setattr(model_mod, "MOCK_MODE", True)
    out = tmp_path / "out"
    pages = out / "frontend" / "src" / "pages"
    pages.mkdir(parents=True)
    (pages / "LandingPage.tsx").write_text(
        "export default function LandingPage() {\n"
        "  return <button>Action</button>\n"
        "}\n",
        encoding="utf-8",
    )
    areas, _ = _areas(mini_task)
    area = next(a for a in areas if a["key"] == "home.png")
    ok = repair_area(model_mod.ModelClient(), out, "LandingPage", area,
                     ["missing accessible name: New blank workbook"])
    assert ok
    content = (pages / "LandingPage.tsx").read_text(encoding="utf-8")
    assert "New blank workbook" in content


def test_repair_area_falls_back_when_script_is_noop(mini_task: Path, tmp_path: Path, monkeypatch) -> None:
    from compiler.repair import repair_area

    monkeypatch.setenv("ARCBENCH_MOCK_MODEL", "1")
    from compiler import model as model_mod

    monkeypatch.setattr(model_mod, "MOCK_MODE", True)
    out = tmp_path / "out"
    pages = out / "frontend" / "src" / "pages"
    pages.mkdir(parents=True)
    # mock patch script replaces '<button>Action</button>' which does not match here,
    # so the script path is a no-op and repair must fall back to the full-file round
    (pages / "LandingPage.tsx").write_text(
        "export default function LandingPage() {\n"
        "  return <button type=\"button\">Action</button>\n"
        "}\n",
        encoding="utf-8",
    )
    areas, _ = _areas(mini_task)
    area = next(a for a in areas if a["key"] == "home.png")
    ok = repair_area(model_mod.ModelClient(), out, "LandingPage", area,
                     ["missing accessible name: New blank workbook"])
    assert ok
    content = (pages / "LandingPage.tsx").read_text(encoding="utf-8")
    assert "New blank workbook" in content


def test_run_patch_script_rejects_broken_script(tmp_path: Path) -> None:
    from compiler.repair import _run_patch_script

    out = tmp_path
    (out / "frontend" / "src" / "pages").mkdir(parents=True)
    target = out / "frontend" / "src" / "pages" / "X.tsx"
    target.write_text("export default function X() { return <div/> }", encoding="utf-8")
    assert not _run_patch_script(out, "raise SystemExit(1)", target.relative_to(out))
    assert not _run_patch_script(out, "1/0", target.relative_to(out))
    ok_script = (
        "from pathlib import Path\n"
        "p = Path('frontend/src/pages/X.tsx')\n"
        "s = p.read_text(encoding='utf-8')\n"
        "p.write_text(s + '\\n// touched', encoding='utf-8')\n"
    )
    assert _run_patch_script(out, ok_script, target.relative_to(out))
