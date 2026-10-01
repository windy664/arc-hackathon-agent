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
