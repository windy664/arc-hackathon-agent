"""Pipeline orchestration: parse -> generate -> assemble -> review -> repair."""

from __future__ import annotations

from pathlib import Path

from .assemble import fallback_backend, fallback_home, write_backend, write_frontend
from .config import BUDGET, MAX_REPAIR_AREAS, log, sdk_event
from .generate import (
    generate_backend,
    generate_design,
    generate_page,
    plan_ui_areas,
)
from .model import ModelClient
from .repair import repair_area, verify_sources
from .requirements import (
    collect_atomics,
    derive_contract,
    find_reference_images,
    load_requirements,
)
from .visual import (
    free_port,
    npm_install_and_build,
    screenshot_pages,
    start_server,
    visual_review,
    wait_for_server,
)


def run(source: Path, out: Path) -> None:
    log(f"requirements: {source}")
    log(f"output: {out}")
    log(f"budget: {BUDGET.status()}")
    sdk_event("mark_run_started", "requirement compiler started")

    data, req_dir = load_requirements(source)
    atomics: list[dict] = []
    collect_atomics(data, [], atomics)
    if not atomics:
        raise SystemExit("no ATOMIC requirements found")
    log(f"atomics: {len(atomics)}")

    images = find_reference_images(atomics, req_dir)
    contract = derive_contract(atomics)
    log(f"reference images: {len(images)}")
    log(f"contract names: {len(contract['accessible_names'])} roles: {contract['aria_roles']}")

    client = ModelClient()
    out.mkdir(parents=True, exist_ok=True)

    design = generate_design(client, atomics)
    log(f"design pages: {len(design.get('pages') or [])} api: {len(design.get('api') or [])} {BUDGET.status()}")

    backend_code = generate_backend(client, design, atomics)
    if backend_code and "express" in backend_code:
        write_backend(out, backend_code)
        log(f"backend written ({len(backend_code)} chars)")
    else:
        write_backend(out, fallback_backend())
        log("backend fallback used")

    areas = plan_ui_areas(atomics, images)
    for area in areas:
        if area["key"] != "core" and area["key"] in images:
            area["images"] = [images[area["key"]]]
        else:
            area["images"] = []
    if len(areas) > 10:
        areas = areas[:10]

    pages: list[tuple[str, str]] = []
    comp_of_area: dict[str, str] = {}
    for area in areas:
        if not BUDGET.allow():
            break
        comp, code = generate_page(client, area, contract)
        if code and ("export" in code or "function" in code):
            pages.append((comp, code))
            comp_of_area[area["key"]] = comp
            log(f"page {comp} written ({len(code)} chars) {BUDGET.status()}")
    if not pages:
        pages.append(("HomePage", fallback_home(contract)))
        comp_of_area[areas[0]["key"]] = "HomePage"

    metas = write_frontend(out, pages, design)
    log("frontend written")

    problems = verify_sources(out, contract, areas, comp_of_area)
    log(f"contract problems: {len(problems)}")
    for p in problems[:8]:
        log(f"  - [{p['area']}] {p['detail']}")

    findings_by_area: dict[str, list[str]] = {}
    for p in problems:
        key = p["area"] or areas[0]["key"]
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
        for area in areas:
            comp = comp_of_area.get(area["key"])
            if not comp or not area.get("images"):
                continue
            if comp not in shots:
                continue
            if not BUDGET.allow() or BUDGET.time_left() < 120:
                break
            verdict = visual_review(client, area["images"][0], shots[comp], area)
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

    sdk_event("mark_implementation_done", f"generated {len(pages)} pages, {BUDGET.status()}")
    sdk_event("mark_run_completed", "requirement compiler finished")
    log(f"done {BUDGET.status()}")
