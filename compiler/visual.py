"""Visual acceptance: build, serve, screenshot, and compare against references."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from .config import log
from .model import ModelClient, extract_json

VISUAL_REVIEW_PROMPT = """You are reviewing a generated web page against its design reference.

The first image is the design reference screenshot from the requirements.
The second image is the screenshot of the generated application at the same area.

Return ONLY a JSON object:
{{
  "ok": true or false,
  "missing_or_wrong": ["concrete difference 1", "..."],
  "controls": ["accessible name of a control that is missing or hard to reach"]
}}

Judge structure, visible labels, control names and flows — not exact colors or fonts.
If the page realises the reference well enough, reply {{"ok": true, "missing_or_wrong": [], "controls": []}}."""


def run_cmd(cmd: list[str], cwd: Path, timeout: int = 300) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
        )
        return proc.returncode, (proc.stdout + proc.stderr)[-6000:]
    except Exception as exc:
        return 1, str(exc)


def npm_install_and_build(out: Path) -> tuple[bool, str]:
    notes = []
    if shutil.which("npm") is None:
        return False, "npm not available"
    code, _ = run_cmd(
        ["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"],
        out / "backend", 600,
    )
    notes.append(f"backend npm install exit={code}")
    code, _ = run_cmd(
        ["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"],
        out / "frontend", 600,
    )
    notes.append(f"frontend npm install exit={code}")
    code, _ = run_cmd(["npm", "run", "build"], out / "frontend", 600)
    notes.append(f"frontend build exit={code}")
    dist = out / "frontend" / "dist"
    return dist.is_dir(), "; ".join(notes)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(out: Path, port: int) -> subprocess.Popen | None:
    env = dict(os.environ)
    env["PORT"] = str(port)
    try:
        return subprocess.Popen(
            ["node", "src/index.js"],
            cwd=str(out / "backend"),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None


def wait_for_server(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


_chromium_bootstrapped = False


def _ensure_chromium() -> bool:
    """Launch chromium, downloading it once if the runtime has no browser yet."""
    global _chromium_bootstrapped
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        pass
    if _chromium_bootstrapped:
        return False
    _chromium_bootstrapped = True
    log("chromium missing; attempting one-time playwright install")
    code, note = run_cmd(
        [sys.executable, "-m", "playwright", "install", "chromium"], Path.cwd(), 600,
    )
    log(f"playwright install exit={code} ({note[-200:]})")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception as exc:
        log(f"chromium still unavailable: {exc}")
        return False


def screenshot_pages(out: Path, metas: list[dict], port: int, shots_dir: Path) -> dict[str, Path]:
    shots: dict[str, Path] = {}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        log(f"playwright unavailable: {exc}")
        return shots
    if not _ensure_chromium():
        return shots
    shots_dir.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:
                log(f"chromium launch failed: {exc}")
                return shots
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            for meta in metas:
                route = meta.get("route") or "/"
                target = f"http://127.0.0.1:{port}{route}"
                try:
                    page.goto(target, wait_until="networkidle", timeout=20000)
                except Exception:
                    try:
                        page.goto(target, wait_until="load", timeout=15000)
                    except Exception as exc:
                        log(f"screenshot goto failed {route}: {exc}")
                        continue
                time.sleep(1.0)
                path = shots_dir / f"{meta['comp']}.png"
                try:
                    page.screenshot(path=str(path), full_page=False)
                    shots[meta["comp"]] = path
                    log(f"screenshot {route} -> {path.name}")
                except Exception as exc:
                    log(f"screenshot failed {route}: {exc}")
            browser.close()
    except Exception as exc:
        log(f"playwright session failed: {exc}")
    return shots


def visual_review(client: ModelClient, reference: Path, screenshot: Path,
                  area: dict) -> dict:
    prompt = VISUAL_REVIEW_PROMPT + (
        f"\n\nThis area covers requirement ids: {', '.join(area.get('req_ids', [])[:6])}"
    )
    raw = client.chat(prompt, system="", images=[reference, screenshot])
    verdict = extract_json(raw)
    if not isinstance(verdict, dict):
        return {
            "ok": False,
            "missing_or_wrong": ["visual review returned no parseable verdict"],
            "controls": [],
        }
    verdict.setdefault("ok", False)
    verdict.setdefault("missing_or_wrong", [])
    verdict.setdefault("controls", [])
    return verdict
