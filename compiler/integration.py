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


def route_table(areas: list[dict]) -> list[dict]:
    """Deterministic routes: the first area owns '/', the rest get /<kebab-comp>."""
    table = []
    for i, area in enumerate(areas):
        comp = comp_name_for(area)
        route = "/" if i == 0 else f"/{kebab(comp)}"
        table.append({
            "key": area["key"],
            "req_ids": area.get("req_ids", []),
            "area": area["reqs"][0]["name"] if area.get("reqs") else area["key"],
            "comp": comp,
            "route": route,
        })
    return table


def build_integration(design: dict, areas: list[dict]) -> dict:
    routes = route_table(areas)
    return {
        "api": design.get("api") or [],
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
        f"- {r['route']} -> {r['area']} (reqs: {', '.join(r['req_ids'][:4])})"
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
