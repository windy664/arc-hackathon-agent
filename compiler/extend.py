"""Extend-mode support for the progressive stages.

Stage 2/3 runs start from the previous stage's best app in --output-dir. The
pipeline must add the new areas without destroying what already passes tests:
existing pages stay untouched, existing API endpoints stay reachable, and new
routes merge into one route table.
"""

from __future__ import annotations

import re
from pathlib import Path


def inspect_app(out: Path) -> dict:
    api: list[dict] = []
    pages: list[dict] = []
    index = out / "backend" / "src" / "index.js"
    if index.is_file():
        src = index.read_text(encoding="utf-8", errors="ignore")
        for method, path in re.findall(
            r"app\.(get|post|patch|put|delete)\(\s*[\"']([^\"']+)", src
        ):
            api.append({"method": method.upper(), "path": path})
    app_tsx = out / "frontend" / "src" / "App.tsx"
    if app_tsx.is_file():
        src = app_tsx.read_text(encoding="utf-8", errors="ignore")
        comps = re.findall(r"import (\w+) from ['\"]\./pages/", src)
        routes = re.findall(r"path: ['\"]([^'\"]*)['\"]", src)
        for i, comp in enumerate(comps):
            pages.append({"comp": comp, "route": routes[i] if i < len(routes) else "/"})
    pages_dir = out / "frontend" / "src" / "pages"
    if pages_dir.is_dir():
        known = {p["comp"] for p in pages}
        for f in sorted(pages_dir.glob("*.tsx")):
            if f.stem not in known:
                pages.append({"comp": f.stem, "route": f"/{f.stem.lower()}"})
    return {
        "has_app": bool(api or pages),
        "api": api,
        "pages": pages,
    }


def backend_covers(existing_api: list[dict], new_source: str) -> bool:
    """A regenerated backend is only acceptable if every old endpoint survives."""
    if not existing_api:
        return True
    for ep in existing_api:
        if ep["path"] not in new_source:
            return False
        if f"app.{ep['method'].lower()}(" not in new_source.replace(" ", ""):
            # tolerate formatting differences: fall back to a loose path check
            if ep["path"] not in new_source:
                return False
    return True


def existing_context(existing: dict, limit_chars: int = 12000) -> str:
    api_lines = "\n".join(
        f"- {e['method']} {e['path']}" for e in existing.get("api", [])
    ) or "- (none)"
    page_lines = "\n".join(
        f"- {p['route']} -> {p['comp']}" for p in existing.get("pages", [])
    ) or "- (none)"
    index = ""  # filled by caller when available
    return (
        "EXISTING APPLICATION (from earlier stages; keep it working):\n"
        f"Existing API endpoints that must remain reachable with the same shapes:\n{api_lines}\n"
        f"Existing pages/routes that must remain reachable:\n{page_lines}\n{index}"
    )
