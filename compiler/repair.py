"""Contract verification, failure-to-area mapping, and bounded repair."""

from __future__ import annotations

import re
from pathlib import Path

from .config import UI_EXTS
from .generate import SYSTEM_PROMPT, digest_requirements
from .model import Conversation, ModelClient, extract_code


def map_problem_to_area(problem: str, areas: list[dict], comp_of_area: dict[str, str]) -> str | None:
    """Route a failure back to the owning UI area (bounded repair scope)."""
    for area in areas:
        for rid in area.get("req_ids", []):
            if rid and rid in problem:
                return area["key"]
    tokens = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,40}", problem))
    for phrase in re.findall(r"(?:name|control|label):\s*([^\"'\n]{3,60})", problem):
        tokens.add(phrase.strip())
    best_key, best_hits = None, 0
    for area in areas:
        blob = " ".join(a.get("description", "") + " " + a.get("name", "") for a in area["reqs"])
        hits = sum(1 for t in tokens if len(t) > 4 and t.casefold() in blob.casefold())
        if hits > best_hits:
            best_key, best_hits = area["key"], hits
    return best_key


def verify_sources(out: Path, contract: dict, areas: list[dict],
                   comp_of_area: dict[str, str]) -> list[dict]:
    problems: list[dict] = []
    corpus: list[str] = []
    for p in (out / "frontend" / "src").rglob("*"):
        if p.is_file() and p.suffix in UI_EXTS:
            corpus.append(p.read_text(encoding="utf-8", errors="ignore"))
    joined = "\n".join(corpus)

    def add(kind: str, detail: str) -> None:
        key = map_problem_to_area(detail, areas, comp_of_area)
        problems.append({"kind": kind, "detail": detail, "area": key})

    for name in contract.get("accessible_names", []):
        token = re.sub(r"<[^>]+>", "", name).strip()
        if not token:
            continue
        head = token.split()[0] if token.split() else token
        if head and head not in joined:
            add("name", f"missing accessible name: {token}")
    for role in contract.get("aria_roles", []):
        if role not in joined:
            add("role", f"missing ARIA role: {role}")
    for attr in contract.get("aria_attributes", []):
        key = attr.split("=")[0]
        if key not in joined:
            add("aria", f"missing aria attribute: {key}")
    return problems


def repair_area(client: ModelClient, out: Path, comp: str, area: dict,
                findings: list[str]) -> bool:
    """One bounded repair round for a single area, using a compacted conversation."""
    target = out / "frontend" / "src" / "pages" / f"{comp}.tsx"
    if not target.is_file():
        for cand in (out / "frontend" / "src").rglob(f"{comp}.tsx"):
            target = cand
            break
    if not target.is_file():
        return False
    source = target.read_text(encoding="utf-8", errors="ignore")

    prefix = (
        f"You previously generated the React component `{comp}.tsx` "
        f"for this UI area:\n{digest_requirements(area.get('reqs', []), 6000)}\n"
        "A review found concrete problems. You will receive the current file and the "
        "problems; return the complete corrected file in one fenced code block."
    )
    conv = Conversation(client, SYSTEM_PROMPT, prefix)
    feedback = "Problems to fix:\n" + "\n".join(f"- {f}" for f in findings[:8])
    prompt = f"{feedback}\n\nCurrent file `{comp}.tsx`:\n{source[:20000]}"
    reply = conv.ask(prompt)
    updated = extract_code(reply)
    if updated and ("function" in updated or "=>" in updated) and updated != source:
        target.write_text(updated, encoding="utf-8")
        return True
    return False
