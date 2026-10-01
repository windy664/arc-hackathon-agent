"""Contract verification, failure-to-area mapping, and bounded repair."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from .config import UI_EXTS
from .generate import SYSTEM_PROMPT, digest_requirements
from .model import Conversation, ModelClient, extract_code, fit_text


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


SCRIPT_REPAIR_PROMPT = """Write a Python script that fixes the listed problems in the file
`{relpath}`. The script runs with `pathlib` and `re` only, reads the file, applies
minimal targeted edits (str.replace or re.sub), and writes the file back. It must
not touch any other file.

Return ONLY one fenced python code block with the complete script — do NOT return
the whole component source; the script contains only the edits.

Problems to fix:
{problems}"""


def _looks_like_patch_script(code: str) -> bool:
    return (
        "write_text" in code
        and "read_text" in code
        and "export default" not in code
    )


def _run_patch_script(out: Path, script: str, relpath: Path) -> bool:
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(out),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return False
    if proc.returncode != 0:
        return False
    target = out / relpath
    if not target.is_file():
        return False
    content = target.read_text(encoding="utf-8", errors="ignore")
    return "function" in content or "=>" in content


def repair_area(client: ModelClient, out: Path, comp: str, area: dict,
                findings: list[str]) -> bool:
    """One bounded repair round for a single area.

    Preferred path: the model returns a small patch script (edits only, so large
    component files never have to round-trip through the context). Fallback: the
    model returns the complete corrected file.
    """
    target = out / "frontend" / "src" / "pages" / f"{comp}.tsx"
    if not target.is_file():
        for cand in (out / "frontend" / "src").rglob(f"{comp}.tsx"):
            target = cand
            break
    if not target.is_file():
        return False
    source = target.read_text(encoding="utf-8", errors="ignore")
    relpath = target.relative_to(out)
    problems = "\n".join(f"- {f}" for f in findings[:8])

    prefix = (
        f"You previously generated the React component `{comp}.tsx` "
        f"for this UI area:\n{digest_requirements(area.get('reqs', []), 6000)}\n"
        "A review found concrete problems."
    )
    conv = Conversation(client, SYSTEM_PROMPT, prefix)

    reply = conv.ask(SCRIPT_REPAIR_PROMPT.format(relpath=relpath.as_posix(), problems=problems))
    script = extract_code(reply)
    if script and _looks_like_patch_script(script) and _run_patch_script(out, script, relpath):
        return True

    prompt = (
        f"Problems to fix:\n{problems}\n\n"
        f"Current file `{comp}.tsx` (may contain elision markers that are NOT content):\n"
        f"{fit_text(source, 20000)}\n\n"
        "Return the complete corrected file in one fenced code block."
    )
    reply = conv.ask(prompt)
    updated = extract_code(reply)
    if updated and ("function" in updated or "=>" in updated) and updated != source:
        target.write_text(updated, encoding="utf-8")
        return True
    return False
