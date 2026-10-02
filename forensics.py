#!/usr/bin/env python3
"""Run forensics and experiment journal.

Usage:
    python3 forensics.py <run_id>          # report + append to EXPERIMENTS.md

Pulls the run's detail and logs, reconstructs the timeline, counts the failure
signatures (timeouts, truncations, rejected regens), and records one journal
row so every iteration leaves a trace instead of relying on memory.
"""

from __future__ import annotations

import http.cookiejar
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import urllib.request
from pathlib import Path

BASE = "https://arc-bench.com"
COOKIE_DB = Path(
    "/home/windy/snap/firefox/common/.mozilla/firefox/euhk2wis.default/cookies.sqlite"
)
JOURNAL = Path(__file__).resolve().parent / "EXPERIMENTS.md"


def make_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    with tempfile.TemporaryDirectory(prefix="arc-cookie-") as temp:
        snapshot = Path(temp) / "cookies.sqlite"
        shutil.copyfile(COOKIE_DB, snapshot)
        snapshot.chmod(0o600)
        wal = COOKIE_DB.with_name(COOKIE_DB.name + "-wal")
        if wal.exists():
            copied = snapshot.with_name(snapshot.name + "-wal")
            shutil.copyfile(wal, copied)
            copied.chmod(0o600)
        con = sqlite3.connect(snapshot.as_uri() + "?mode=ro", uri=True, timeout=5)
        rows = con.execute(
            "SELECT host,path,isSecure,expiry,name,value FROM moz_cookies "
            "WHERE host IN ('arc-bench.com','.arc-bench.com')"
        ).fetchall()
        con.close()
    for host, path, secure, expiry, name, value in rows:
        jar.set_cookie(http.cookiejar.Cookie(
            0, name, value, None, False, host, host.startswith("."),
            host.startswith("."), path, True, bool(secure), expiry or None,
            False, None, None, {}, False,
        ))
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def fetch(opener, path: str) -> bytes:
    req = urllib.request.Request(
        BASE + path, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with opener.open(req, timeout=60) as resp:
        return resp.read()


def analyze(detail: dict, text: str) -> dict:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    stamps = re.findall(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", text)
    timeouts = sum(1 for ln in lines if "timed out" in ln or "timeout" in ln.lower())
    truncations = sum(1 for ln in lines if "truncated" in ln)
    rejects = sum(1 for ln in lines if "rejected" in ln or "fallback used" in ln)
    telemetry = [ln for ln in lines if "telemetry" in ln]
    latencies = [int(m) for ln in telemetry
                 for m in re.findall(r"latency=(\d+)s", ln)]
    groups = re.findall(r"(designed|implemented) (REQ-[\w-]+)", text)
    blockers = [ln for ln in lines if "error" in ln.lower() or "rejected" in ln][:12]
    return {
        "span": f"{stamps[0]} -> {stamps[-1]}" if stamps else "?",
        "log_lines": len(lines),
        "timeouts": timeouts,
        "truncations": truncations,
        "rejected_or_fallback": rejects,
        "max_latency_s": max(latencies) if latencies else 0,
        "median_latency_s": sorted(latencies)[len(latencies) // 2] if latencies else 0,
        "nodes_walked": [f"{a} {b}" for a, b in groups],
        "first_blockers": blockers,
    }


def journal_row(detail: dict, stats: dict, git_rev: str) -> str:
    return (
        f"| {detail.get('created_at', '?')[:10]} | `{git_rev}` | `{detail.get('id')}` "
        f"| {detail.get('requirement_id')} | {detail.get('status')} "
        f"| {detail.get('run_duration_seconds', 0) // 60}m "
        f"| {(detail.get('token_count') or 0) / 1e6:.1f}M "
        f"| ¥{detail.get('token_cost_usd') or 0:.2f} "
        f"| {detail.get('test_pass_rate') or 0}% "
        f"| to={stats['timeouts']} tr={stats['truncations']} rj={stats['rejected_or_fallback']} "
        f"| p50={stats['median_latency_s']}s max={stats['max_latency_s']}s |\n"
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 forensics.py <run_id>")
    run_id = sys.argv[1]
    opener = make_opener()
    detail = json.loads(fetch(opener, f"/api/runs/{run_id}"))
    logs_raw = fetch(opener, f"/api/runs/{run_id}/logs")
    logs = json.loads(logs_raw)
    text = "\n".join(
        str(logs.get(k) or "") for k in ("stdout", "stderr", "console")
    )
    stats = analyze(detail, text)

    print(f"run        : {run_id}  status={detail.get('status')}")
    print(f"task       : {detail.get('requirement_id')}")
    print(f"duration   : {(detail.get('run_duration_seconds') or 0) // 60}m")
    print(f"tokens/cost: {(detail.get('token_count') or 0) / 1e6:.1f}M / ¥{detail.get('token_cost_usd') or 0:.2f}")
    print(f"tests      : pass={detail.get('passed_count')} fail={detail.get('failed_count')} "
          f"rate={detail.get('test_pass_rate')}%")
    print(f"span       : {stats['span']}")
    print(f"signatures : timeouts={stats['timeouts']} truncations={stats['truncations']} "
          f"rejected/fallback={stats['rejected_or_fallback']}")
    print(f"latency    : p50={stats['median_latency_s']}s max={stats['max_latency_s']}s")
    print(f"tree walk  : {len(stats['nodes_walked'])} steps")
    if stats["first_blockers"]:
        print("first blockers:")
        for ln in stats["first_blockers"][:8]:
            print("  ", ln.strip()[:160])

    import subprocess

    git_rev = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, cwd=Path(__file__).parent,
    ).stdout.strip() or "?"
    if not JOURNAL.is_file():
        JOURNAL.write_text(
            "# Experiment journal\n\n"
            "| date | commit | run | task | status | dur | tokens | cost | pass% | signatures | latency |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(journal_row(detail, stats, git_rev))
    print(f"journal row appended -> {JOURNAL}")


if __name__ == "__main__":
    main()
