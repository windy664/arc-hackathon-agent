"""The integration contract shared by all parallel engineers.

Parallel areas only cohere into one app if every engineer agrees on the API
surface, the route table, and the seeded data — the requirement scenarios
cross area boundaries (create here, visible there, persisted after refresh),
so these three things are team-wide context, not per-area guesses.
"""

from __future__ import annotations

import json
import re


def comp_name_for(area: dict) -> str:
    name = (area["reqs"][0]["name"] or "Page") if area.get("reqs") else "Page"
    comp = re.sub(r"[^A-Za-z0-9]", "", name.title())[:24]
    return comp or "Page"


def kebab(name: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "page"


def route_table(areas: list[dict], root_taken: bool = False) -> list[dict]:
    """Deterministic routes. The first area owns '/' unless an earlier-stage
    page already owns it (extend mode), in which case everything gets slugs.
    """
    table = []
    for i, area in enumerate(areas):
        comp = comp_name_for(area)
        route = "/" if (i == 0 and not root_taken) else f"/{kebab(comp)}"
        table.append({
            "key": area["key"],
            "req_ids": area.get("req_ids", []),
            "area": area["reqs"][0]["name"] if area.get("reqs") else area["key"],
            "comp": comp,
            "route": route,
        })
    return table


def build_integration(design: dict, areas: list[dict],
                      existing_pages: list[dict] | None = None,
                      existing_api: list[dict] | None = None) -> dict:
    existing_pages = existing_pages or []
    root_taken = any(p.get("route") == "/" for p in existing_pages)
    routes = [dict(p) for p in existing_pages] + route_table(areas, root_taken=root_taken)
    api = [dict(e) for e in (existing_api or [])]
    seen = {(e.get("method"), e.get("path")) for e in api}
    for a in (design.get("api") or []):
        key = (a.get("method"), a.get("path"))
        if key not in seen:
            api.append(a)
            seen.add(key)
    return {
        "api": api,
        "seed": design.get("seed") or {},
        "routes": routes,
        "data_ownership": design.get("data_ownership") or [],
    }


def digest_integration(integration: dict) -> str:
    """Compact team-wide context for every engineer prefix."""
    api_lines = "\n".join(
        f"- {a.get('method', 'GET')} {a.get('path', '')} : {a.get('summary', '')}"
        for a in integration.get("api", [])
    ) or "- (none)"
    route_lines = "\n".join(
        f"- {r.get('route')} -> {r.get('area') or r.get('comp') or '?'} "
        f"(reqs: {', '.join((r.get('req_ids') or [])[:4]) or 'earlier stage'})"
        for r in integration.get("routes", [])
    )
    seed = json.dumps(integration.get("seed", {}), ensure_ascii=False)
    ownership_lines = "\n".join(
        f"- {o.get('entity', '?')}.{', '.join(o.get('fields', []) or ['*'])}"
        f" -> written by {', '.join(o.get('writes') or o.get('req_ids') or ['?'])}"
        for o in integration.get("data_ownership", [])
        if isinstance(o, dict)
    ) or "- (none declared)"
    return (
        "TEAM INTEGRATION CONTRACT (all engineers must obey):\n"
        f"API surface (fetch these exact endpoints):\n{api_lines}\n"
        f"Route table (link to these exact routes):\n{route_lines}\n"
        f"Seed data (the app is pre-populated with exactly this):\n{seed}\n"
        "Field ownership (write zones are separated at field level):\n"
        f"{ownership_lines}\n"
        "Write-separation rule: your area may only create/update fields it owns "
        "(marked written by your requirement ids); fields owned by other areas "
        "are read-only for you — read them through the API, never mutate them.\n"
        "Cross-area rules: after create/edit flows the user may navigate back to "
        "other routes above; state must persist via the API, and every visible "
        "entry point named in the requirements must exist on its route."
    )


def area_scenario_digest(area: dict, limit_chars: int = 8000) -> str:
    rows = []
    for a in area.get("reqs", []):
        for sc in (a.get("scenarios") or [])[:2]:
            steps = " ".join(
                f"{s.get('keyword', '')}: {s.get('content', '')}"
                for s in (sc.get("steps") or [])[:4]
            )
            rows.append(f"- [{a.get('id')}] {steps[:700]}")
    return "\n".join(rows)[:limit_chars]
