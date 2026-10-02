"""Generation stages: design, backend, and per-area UI pages."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .model import ModelClient, extract_code, extract_json

SYSTEM_PROMPT = (
    "You are a senior full-stack engineer. You generate complete, runnable web "
    "applications from structured requirements. Follow the stated accessibility "
    "contract exactly (ARIA roles, accessible names, visible labels). Output only "
    "the requested code inside a single fenced code block."
)


def digest_requirements(atomics: list[dict], limit_chars: int = 24000) -> str:
    parts = []
    for a in atomics:
        desc = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", a["description"]).strip()
        parts.append(f"### {a['id']} {a['name']}\n{desc[:1200]}")
    return "\n\n".join(parts)[:limit_chars]


def scenario_digest(atomics: list[dict]) -> str:
    rows = []
    for a in atomics:
        for sc in (a.get("scenarios") or [])[:2]:
            steps = " ".join(
                f"{s.get('keyword', '')}: {s.get('content', '')}" for s in (sc.get("steps") or [])[:4]
            )
            rows.append(f"- [{a['id']}] {steps[:700]}")
    return "\n".join(rows)[:16000]


def plan_ui_areas(atomics: list[dict], images: dict[str, Path]) -> list[dict]:
    """Group atomic requirements by the reference image nearest to them."""
    areas: dict[str, dict] = {}
    order: list[str] = []
    for a in atomics:
        key = "core"
        for rel in re.findall(r"reference/([\w./-]+\.png)", a["description"]):
            if rel in images:
                key = rel
                break
        if key not in areas:
            areas[key] = {"key": key, "reqs": [], "req_ids": []}
            order.append(key)
        areas[key]["reqs"].append(a)
        areas[key]["req_ids"].append(a["id"])
    return [areas[k] for k in order]


BACKEND_SPEC_PROMPT = (
    """Design the REST API for the application described below.

Return ONLY a JSON object with exactly this shape (example keys):
{
  "seed": {"<entity>": [{"<field>": <value>}]},
  "api": [{"method": "GET", "path": "/api/...", "summary": "..."}],
  "pages": [{"route": "/...", "name": "...", "summary": "..."}],
  "data_ownership": [{"entity": "<entity>", "fields": ["<field>"], "req_ids": ["REQ-x"], "writes": ["REQ-x"]}]
}

In data_ownership, assign every entity field to the requirement ids that create
or update it (writes) so that parallel implementers never touch another area's
fields. Other areas may read those fields through the API.

Requirements digest:
{reqs}

Seed data mentioned in scenarios (create records so the app works out of the box):
{scenarios}
"""
    .replace("{", "{{").replace("}", "}}")
    .replace("{{reqs}}", "{reqs}")
    .replace("{{scenarios}}", "{scenarios}")
)

BACKEND_CODE_PROMPT = """Write the complete Express backend implementing this API design.

Rules:
- CommonJS, single file `index.js`, dependencies: express, cors, better-sqlite3.
- Listen on `process.env.PORT || 3000`.
- Serve `../frontend/dist` statically and fall back to index.html for client routes.
- Persist data with better-sqlite3 in-memory + seed so state survives within one process.
- Seed records must match the design's `seed` section exactly.
- Validation errors respond 400 with an `errors` object keyed by field name.

API design JSON:
{design}

Requirements digest (for behaviour and error messages):
{reqs}

Return ONLY one fenced code block containing the full file content of `index.js`."""

FRONTEND_PAGE_PROMPT = """Create a React page component implementing this UI area.

Rules:
- The file must default-export a React component named `{comp}` using hooks and fetch() against /api.
- Honour the accessibility contract exactly: ARIA roles and accessible names as written in the requirements.
- Every interactive control must be reachable by its accessible name (button/link/textbox names).
- Use inline styles or className strings; no external UI library.
- TypeScript, imports only from 'react'.
- The reference screenshot shows the target layout — match its structure, labels and flows.

Area: {area}
Requirements:
{reqs}

Accessibility contract to respect: {contract}

Return ONLY one fenced code block containing the full file content of `{comp}.tsx`."""


def generate_design(client: ModelClient, atomics: list[dict]) -> dict:
    prompt = BACKEND_SPEC_PROMPT.format(
        reqs=digest_requirements(atomics, 16000),
        scenarios=scenario_digest(atomics),
    )
    return extract_json(client.chat(prompt, system=SYSTEM_PROMPT))


def generate_backend(client: ModelClient, design: dict, atomics: list[dict]) -> str:
    prompt = BACKEND_CODE_PROMPT.format(
        design=json.dumps(design, ensure_ascii=False)[:12000],
        reqs=digest_requirements(atomics, 14000),
    )
    return extract_code(client.chat(prompt, system=SYSTEM_PROMPT))


def generate_page(client: ModelClient, area: dict, contract: dict) -> tuple[str, str]:
    comp = re.sub(r"[^A-Za-z0-9]", "", (area["reqs"][0]["name"] or "Page").title())[:24] or "Page"
    images = area.get("images") or []
    prompt = FRONTEND_PAGE_PROMPT.format(
        comp=comp,
        area=area.get("key", "core"),
        reqs=digest_requirements(area["reqs"], 12000),
        contract=json.dumps(contract, ensure_ascii=False)[:3000],
    )
    code = extract_code(client.chat(prompt, system=SYSTEM_PROMPT, images=images or None))
    return comp, code
