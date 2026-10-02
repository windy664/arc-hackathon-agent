"""Pipeline orchestration: parse -> generate -> assemble -> review -> repair."""

from __future__ import annotations

import json
from pathlib import Path

from .agents import EngineerTeam, ReviewerTeam
from .assemble import fallback_backend, fallback_home, write_backend, write_frontend
from .config import BUDGET, MAX_REPAIR_AREAS, log
from .extend import backend_covers, existing_context, inspect_app
from .generate import (
    generate_backend,
    generate_design,
    plan_ui_areas,
)
from .integration import build_integration
from .model import ModelClient
from .repair import repair_area, verify_sources
from .report import Reporter
from .requirements import (
    collect_atomics,
    derive_contract,
    find_reference_images,
    load_requirements,
    plan_design_groups,
)
from .visual import (
    free_port,
    npm_install_and_build,
    screenshot_pages,
    start_server,
    wait_for_server,
)


def run(source: Path, out: Path) -> None:
    log(f"requirements: {source}")
    log(f"output: {out}")
    log(f"budget: {BUDGET.status()}")
    reporter = Reporter(out)
    reporter.run_started("requirement compiler started")

    data, req_dir = load_requirements(source)
    atomics: list[dict] = []
    collect_atomics(data, [], atomics)
    if not atomics:
        raise SystemExit("no ATOMIC requirements found")
    log(f"atomics: {len(atomics)}")
    reporter.store_tree(data)

    images = find_reference_images(atomics, req_dir)
    contract = derive_contract(atomics)
    log(f"reference images: {len(images)}")
    log(f"contract names: {len(contract['accessible_names'])} roles: {contract['aria_roles']}")

    client = ModelClient()
    out.mkdir(parents=True, exist_ok=True)

    existing = inspect_app(out)
    extend_mode = existing["has_app"]
    if extend_mode:
        log(f"extend mode: {len(existing['pages'])} existing pages, "
            f"{len(existing['api'])} existing endpoints")

    groups = plan_design_groups(atomics)
    log(f"design groups (tree units): {[g['node_id'] for g in groups]}")

    cum_design: dict = {"api": [], "seed": {}, "pages": [], "data_ownership": []}
    integration: dict = build_integration(
        cum_design, [],
        existing_pages=existing["pages"] if extend_mode else None,
        existing_api=existing["api"] if extend_mode else None,
    )

    pages: list[tuple[str, str]] = []
    comp_of_area: dict[str, str] = {}
    all_areas: list[dict] = []

    for group in groups:
        if not BUDGET.allow():
            log(f"budget exhausted before {group['node_id']}")
            break
        g_ids = [a["id"] for a in group["atomics"]]
        reporter.design_started(g_ids, f"designing {group['node_id']}")

        note = existing_context(existing) if extend_mode else ""
        if cum_design["api"] or cum_design["seed"]:
            note += (
                "\n\nALREADY DESIGNED earlier in the tree walk (keep shapes; only "
                "extend): "
                + json.dumps({"api": cum_design["api"], "seed": cum_design["seed"]},
                             ensure_ascii=False)[:4000]
            )
        d = generate_design(client, group["atomics"], existing_note=note)

        seen = {(a.get("method"), a.get("path")) for a in cum_design["api"]}
        for a in (d.get("api") or []):
            if (a.get("method"), a.get("path")) not in seen:
                cum_design["api"].append(a)
                seen.add((a.get("method"), a.get("path")))
        cum_design["seed"].update(d.get("seed") or {})
        cum_design["data_ownership"] += (d.get("data_ownership") or [])
        cum_design["pages"] += (d.get("pages") or [])
        reporter.design_done(g_ids, f"{group['node_id']} design complete")
        log(f"designed {group['node_id']}: +{len(d.get('api') or [])} api {BUDGET.status()}")

        areas = plan_ui_areas(group["atomics"], images)
        for area in areas:
            if area["key"] != "core" and area["key"] in images:
                area["images"] = [images[area["key"]]]
            else:
                area["images"] = []
        if len(areas) > 10:
            areas = areas[:10]
        all_areas += areas

        integration = build_integration(
            cum_design, areas,
            existing_pages=integration.get("routes"),
            existing_api=integration.get("api"),
        )
        team = EngineerTeam(client, contract, integration=integration)
        for area, comp, code in team.build_all(areas):
            if code and ("export" in code or "function" in code):
                pages.append((comp, code))
                comp_of_area[area["key"]] = comp
                log(f"page {comp} written ({len(code)} chars) {BUDGET.status()}")
                reporter.implement_started(area["req_ids"], f"generating {comp}")
                reporter.implement_done(area["req_ids"], f"{comp} generated")
                reporter.interface(
                    f"{area['req_ids'][0]}.UI.{comp}" if area["req_ids"] else f"UI.{comp}",
                    area["req_ids"],
                    f"UI area {area['key']} rendered by {comp}",
                    f"frontend/src/pages/{comp}.tsx",
                )
        log(f"implemented {group['node_id']} {BUDGET.status()}")

    areas = all_areas
    if not pages:
        pages.append(("HomePage", fallback_home(contract)))
        if areas:
            comp_of_area[areas[0]["key"]] = "HomePage"

    # the backend is one shared artifact — generate it once from the
    # cumulative tree design instead of per node (each per-node regen used to
    # burn a full timeout cycle on the slow gateway)
    index = out / "backend" / "src" / "index.js"
    existing_src = index.read_text(encoding="utf-8", errors="ignore") if index.is_file() else None
    prev_api = [dict(e) for e in integration.get("api") or []]
    backend_code = generate_backend(client, cum_design, atomics, existing_src=existing_src)
    if backend_code and "express" in backend_code and (
        not existing_src or backend_covers(prev_api, backend_code)
    ):
        write_backend(out, backend_code)
        log(f"backend written ({len(backend_code)} chars)")
    elif existing_src:
        log("backend regen rejected; keeping existing backend")
    else:
        write_backend(out, fallback_backend())
        log("backend fallback used")

    metas = write_frontend(
        out, pages, integration,
        keep_comps=existing["pages"] if extend_mode else None,
    )
    log("frontend written")

    problems = verify_sources(out, contract, areas, comp_of_area)
    log(f"contract problems: {len(problems)}")
    for p in problems[:8]:
        log(f"  - [{p['area']}] {p['detail']}")

    findings_by_area: dict[str, list[str]] = {}
    for p in problems:
        key = p["area"] or (areas[0]["key"] if areas else None)
        findings_by_area.setdefault(key, []).append(p["detail"])

    # ---- visual acceptance: build, serve, screenshot, compare ----
    if BUDGET.allow() and BUDGET.time_left() > 240:
        ok_build, build_note = npm_install_and_build(out)
        log(f"build: {ok_build} ({build_note})")
        server = None
        shots: dict[str, Path] = {}
        if ok_build:
            port = free_port()
            server = start_server(out, port)
            if server and wait_for_server(port):
                shots = screenshot_pages(out, metas, port, out / "artifacts" / "screenshots")
            else:
                log("server did not become ready; skipping screenshots")
        review_items = []
        for area in areas:
            comp = comp_of_area.get(area["key"])
            if not comp or not area.get("images") or comp not in shots:
                continue
            if not BUDGET.allow() or BUDGET.time_left() < 120:
                break
            review_items.append((area, area["images"][0], shots[comp], comp))
        reviewers = ReviewerTeam(client)
        for (area, _ref, _shot, comp), verdict in zip(
            review_items, reviewers.review_all([i[:3] for i in review_items])
        ):
            status = "OK" if verdict.get("ok") else f"{len(verdict.get('missing_or_wrong', []))} diffs"
            log(f"visual review {comp}: {status} {BUDGET.status()}")
            if not verdict.get("ok"):
                findings = [str(x) for x in verdict.get("missing_or_wrong", []) if x]
                findings += [
                    f"missing or unreachable control: {c}"
                    for c in verdict.get("controls", []) if c
                ]
                if findings:
                    findings_by_area.setdefault(area["key"], []).extend(findings)
        if server:
            server.terminate()
            try:
                server.wait(timeout=5)
            except Exception:
                server.kill()

    # ---- one bounded repair round per failing area ----
    if findings_by_area and BUDGET.allow() and BUDGET.time_left() > 120:
        ordered = sorted(findings_by_area.items(), key=lambda kv: -len(kv[1]))[:MAX_REPAIR_AREAS]
        changed = 0
        for key, findings in ordered:
            if not BUDGET.allow() or BUDGET.time_left() < 60:
                break
            comp = comp_of_area.get(key)
            area = next((a for a in areas if a["key"] == key), areas[0])
            if comp and repair_area(client, out, comp, area, findings):
                changed += 1
                log(f"repaired {comp}.tsx ({len(findings)} findings)")
        log(f"repair round changed {changed} areas {BUDGET.status()}")
        if changed and BUDGET.time_left() > 180:
            ok_build, build_note = npm_install_and_build(out)
            log(f"rebuild after repair: {ok_build} ({build_note})")

    # ---- final (free) re-check drives the reported test state per area ----
    final_problems = verify_sources(out, contract, areas, comp_of_area)
    failing_areas = {p["area"] or (areas[0]["key"] if areas else None) for p in final_problems}
    for key, findings in findings_by_area.items():
        if findings:
            failing_areas.add(key)
    for area in areas:
        if area["key"] in failing_areas:
            reporter.test_failed(area["req_ids"], "contract or visual review not satisfied")
        elif area["req_ids"]:
            reporter.test_passed(area["req_ids"], "contract and visual review satisfied")
    log(f"final contract problems: {len(final_problems)}")
    reporter.run_completed(f"generated {len(pages)} pages, {BUDGET.status()}")
    log(f"done {BUDGET.status()}")
