from pathlib import Path

import pytest

from compiler.requirements import (
    collect_atomics,
    derive_contract,
    find_reference_images,
    load_requirements,
)


def test_load_and_collect(mini_task: Path) -> None:
    data, req_dir = load_requirements(mini_task)
    atomics: list[dict] = []
    collect_atomics(data, [], atomics)
    assert [a["id"] for a in atomics] == ["REQ-1-1"]
    assert req_dir == mini_task


def test_contract_extraction(mini_task: Path) -> None:
    data, req_dir = load_requirements(mini_task)
    atomics: list[dict] = []
    collect_atomics(data, [], atomics)
    contract = derive_contract(atomics)
    assert "New blank workbook" in contract["accessible_names"]
    assert "grid" in contract["aria_roles"]
    assert any(a.startswith("aria-selected") for a in contract["aria_attributes"])


def test_reference_images(mini_task: Path) -> None:
    data, req_dir = load_requirements(mini_task)
    atomics: list[dict] = []
    collect_atomics(data, [], atomics)
    images = find_reference_images(atomics, req_dir)
    assert "home.png" in images
    assert images["home.png"].is_file()


@pytest.mark.parametrize("task", ["hackathon--sheet", "hackathon--github"])
def test_real_tasks(real_tasks_root: Path, task: str) -> None:
    src = real_tasks_root / task
    if not src.is_dir():
        pytest.skip(f"real task pack not present: {src}")
    data, req_dir = load_requirements(src)
    atomics: list[dict] = []
    collect_atomics(data, [], atomics)
    assert len(atomics) >= 10
    images = find_reference_images(atomics, req_dir)
    assert len(images) >= 5
    contract = derive_contract(atomics)
    assert len(contract["accessible_names"]) >= 10
