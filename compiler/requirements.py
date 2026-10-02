"""Requirements tree parsing and runtime UI-contract extraction."""

from __future__ import annotations

import re
from pathlib import Path


def load_requirements(source: Path) -> tuple[dict, Path]:
    yaml_path = source
    if source.is_dir():
        candidates = [source / "requirements.yaml", source / "requirements.yml"]
        candidates += sorted(source.glob("*.yaml"))
        yaml_path = next((p for p in candidates if p.is_file()), source / "requirements.yaml")
    text = yaml_path.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:
        raise SystemExit("pyyaml is required (declared in requirements.txt)")
    return yaml.safe_load(text), yaml_path.parent


def collect_atomics(node: dict, trail: list[str], out: list[dict],
                    parent_id: str | None = None) -> None:
    name = node.get("name") or node.get("id") or ""
    node_id = node.get("id") or "ROOT"
    if node.get("type") == "ATOMIC":
        out.append({
            "id": node.get("id"),
            "name": name,
            "parent": parent_id or "ROOT",
            "trail": " / ".join(trail),
            "description": node.get("description") or "",
            "scenarios": node.get("scenarios") or [],
        })
    for child in node.get("children") or []:
        collect_atomics(child, trail + [name], out, parent_id=node_id)


def plan_design_groups(atomics: list[dict]) -> list[dict]:
    """Group atomics by their parent folder in tree order.

    Each group is one design unit: design it (with full fidelity for its
    scope), implement its areas, then move down the tree — matching the
    requirement tree's per-node design -> implement -> test lifecycle.
    """
    groups: dict[str, dict] = {}
    order: list[str] = []
    for a in atomics:
        pid = a.get("parent") or "ROOT"
        if pid not in groups:
            groups[pid] = {"node_id": pid, "atomics": []}
            order.append(pid)
        groups[pid]["atomics"].append(a)
    return [groups[k] for k in order]


def find_reference_images(atomics: list[dict], req_dir: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for atom in atomics:
        for rel in re.findall(r"reference/([\w./-]+\.png)", atom["description"]):
            p = req_dir / "reference" / Path(rel).name
            if not p.is_file():
                p = req_dir / rel
            if p.is_file():
                found[rel] = p
    return found


def derive_contract(atomics: list[dict]) -> dict:
    """Extract the UI contract (a11y names, ARIA roles/attrs) from requirement text."""
    texts = [re.sub(r"\s+", " ", a["description"]) for a in atomics]
    names: set[str] = set()
    roles: set[str] = set()
    aria: set[str] = set()
    quoted = r"[\"'\u201c\u201d\u2018\u2019]([^\"'\u201c\u201d\u2018\u2019]{1,80})[\"'\u201c\u201d\u2018\u2019]"
    for text in texts:
        for m in re.finditer(r"accessible name (?:is |of |as |is exactly )?" + quoted, text):
            names.add(m.group(1))
        for m in re.finditer(r"accessible names? \(for example, ([^)]+)\)", text):
            names.add(m.group(1).split(",")[0].strip())
        for m in re.finditer(r"(?:button|link|tab|menu item|dialog|field|input|text box|control)"
                             r"[^.\n]{0,60}?(?:named|is named|labelled|labeled) " + quoted, text):
            names.add(m.group(1))
        for m in re.finditer(r"(?:submit|action) button[^.\n]{0,40}?named " + quoted, text):
            names.add(m.group(1))
        for m in re.finditer(r"ARIA (\w+) role", text):
            roles.add(m.group(1))
        for m in re.finditer(r"(aria-[a-z]+(?:=\"[^\"]*\")?)", text):
            aria.add(m.group(1))
    names = {" ".join(n.split()) for n in names
             if not n.startswith(("REQ", "http", "the ", "a ")) and "<" not in n[:2]}
    return {
        "accessible_names": sorted(names),
        "aria_roles": sorted(roles),
        "aria_attributes": sorted(aria),
    }
