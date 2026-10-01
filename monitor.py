#!/usr/bin/env python3
"""
ARC-Bench run monitor — 每 3 分钟轮询一次运行状态：
1. 拉取 /api/runs/<id>（token_count、token_cost_usd、node_states、status）
2. 下载 /api/runs/<id>/logs 日志快照，按 chars/4 交叉估算 token
3. 计算消耗速率、外推最终费用，超阈值告警

用法:
  python3 monitor.py <run_id> [--interval 180] [--budget-cny 500]
                     [--warn-cny 8] [--stop-cny 15] [--outdir /tmp/arc-monitor]
"""
import argparse
import http.cookiejar
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

BASE = "https://arc-bench.com"
COOKIE_DB = Path(
    "/home/windy/snap/firefox/common/.mozilla/firefox/euhk2wis.default/cookies.sqlite"
)


def make_opener():
    jar = http.cookiejar.CookieJar()
    with tempfile.TemporaryDirectory(prefix="arc-cookie-read-") as temp:
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
        jar.set_cookie(
            http.cookiejar.Cookie(
                0, name, value, None, False, host, host.startswith("."),
                host.startswith("."), path, True, bool(secure), expiry or None,
                False, None, None, {}, False,
            )
        )
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def fetch(opener, path):
    req = urllib.request.Request(
        BASE + path,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/html,*/*"},
    )
    with opener.open(req, timeout=60) as resp:
        return resp.read()


def estimate_tokens_from_logs(raw: bytes) -> int:
    try:
        payload = json.loads(raw)
    except Exception:
        return max(len(raw) // 4, 0)
    text = ""
    if isinstance(payload, dict):
        for key in ("stdout", "stderr", "console"):
            v = payload.get(key)
            if isinstance(v, str):
                text += v
            elif isinstance(v, list):
                text += "\n".join(str(x) for x in v)
        for key in ("events", "runner_events", "runner_event_lines", "visual_events"):
            v = payload.get(key)
            if isinstance(v, str):
                text += v
            elif isinstance(v, list):
                text += "\n".join(json.dumps(x) if not isinstance(x, str) else x for x in v)
    else:
        text = raw.decode("utf-8", "replace")
    return max(len(text) // 4, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--interval", type=int, default=180)
    ap.add_argument("--budget-cny", type=float, default=500.0)
    # efficient per-run band on the leaderboard is ~1-3 CNY (Iris 0.1, gaoyu06 1,
    # pingguomiaomiao 2); warn early, stop before a run eats the team budget.
    ap.add_argument("--warn-cny", type=float, default=8.0)
    ap.add_argument("--stop-cny", type=float, default=15.0)
    ap.add_argument("--outdir", default="/tmp/arc-monitor")
    args = ap.parse_args()

    outdir = Path(args.outdir) / args.run_id
    outdir.mkdir(parents=True, exist_ok=True)
    opener = make_opener()

    start = time.time()
    last_tokens = 0
    warned = False
    stop_signalled = False
    history = []

    print(f"[monitor] watching run {args.run_id} every {args.interval}s")
    print(f"[monitor] budget={args.budget_cny} CNY warn={args.warn_cny} stop={args.stop_cny}")
    print(f"[monitor] snapshots -> {outdir}")

    while True:
        cycle = time.time()
        try:
            detail_raw = fetch(opener, f"/api/runs/{args.run_id}")
            logs_raw = fetch(opener, f"/api/runs/{args.run_id}/logs")
        except Exception as exc:
            print(f"[monitor] fetch error: {exc}; retrying")
            time.sleep(args.interval)
            continue

        detail_path = outdir / "detail.json"
        detail_path.write_bytes(detail_raw)
        logs_path = outdir / f"logs-{int(cycle)}.json"
        logs_path.write_bytes(logs_raw)
        latest = outdir / "logs-latest.json"
        shutil.copyfile(logs_path, latest)

        try:
            detail = json.loads(detail_raw)
        except Exception:
            print("[monitor] bad detail payload; retrying")
            time.sleep(args.interval)
            continue

        tokens = int(detail.get("token_count") or 0)
        cost = float(detail.get("token_cost_usd") or 0.0)  # 实际单位 CNY
        status = detail.get("status")
        passed = detail.get("passed_count") or 0
        failed = detail.get("failed_count") or 0
        duration = float(detail.get("run_duration_seconds") or 0.0)
        est_from_logs = estimate_tokens_from_logs(logs_raw)

        elapsed = time.time() - start
        dtokens = tokens - last_tokens
        rate = dtokens / args.interval if args.interval else 0.0
        cost_rate = (cost / elapsed * 3600) if elapsed > 0 else 0.0
        remaining_budget = args.budget_cny - cost
        if cost > 0 and elapsed > 0:
            projected = cost / max(duration, 1.0) * max(duration, elapsed)
        else:
            projected = cost

        node_states = detail.get("node_states") or {}
        done_nodes = sum(1 for v in node_states.values() if v not in ("default", None))

        rec = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "tokens": tokens,
            "cost_cny": cost,
            "log_est_tokens": est_from_logs,
            "tokens_per_sec": rate,
            "cost_per_hour_cny": cost_rate,
            "passed": passed,
            "failed": failed,
            "duration_s": duration,
            "nodes_done": done_nodes,
            "nodes_total": len(node_states),
        }
        history.append(rec)
        (outdir / "history.json").write_text(json.dumps(history, indent=2))

        print(
            f"[monitor] {rec['ts']} status={status} tokens={tokens:,} "
            f"cost={cost:.2f}CNY rate={rate/1000:.0f}k tok/s "
            f"~{cost_rate:.1f}CNY/h log-est={est_from_logs:,} "
            f"tests={passed}/{passed+failed} nodes={done_nodes}/{len(node_states)} "
            f"proj={projected:.0f}CNY"
        )

        if cost >= args.warn_cny and not warned:
            warned = True
            print(f"[monitor] !! WARN: cost {cost:.2f} CNY >= {args.warn_cny} CNY")

        if cost >= args.stop_cny and not stop_signalled:
            stop_signalled = True
            print(
                f"[monitor] !! STOP THRESHOLD: cost {cost:.2f} CNY >= {args.stop_cny} CNY "
                f"— cancel the run on the platform now to protect the {args.budget_cny} CNY budget"
            )
            (outdir / "STOP_THRESHOLD_REACHED").write_text(
                f"cost={cost} at {rec['ts']}\n"
            )

        if status in ("FAILED", "COMPLETED", "SUCCESS", "CANCELLED", "ERROR", "TIMEOUT"):
            print(f"[monitor] run finished with status={status}; stopping monitor")
            break

        last_tokens = tokens
        wait = args.interval - (time.time() - cycle)
        if wait > 0:
            time.sleep(wait)


if __name__ == "__main__":
    main()
