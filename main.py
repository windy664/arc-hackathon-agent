#!/usr/bin/env python3
"""ARC-Bench requirement compiler.

Runtime pipeline (nothing about the target product is baked in):

1. Parse the requirements tree given on the command line.
2. Derive a UI/a11y contract and seed values from the requirement text itself.
3. Design the app, generate the backend and each UI area with the reference
   screenshots attached (vision model when provided).
4. Build the app, screenshot every page, and compare each screenshot against its
   reference image with the vision model (visual acceptance).
5. Map each failure back to the owning UI area, run one bounded repair round per
   area with a compacted conversation, rebuild, and exit 0.

Platform contract: output root must contain frontend/ and backend/; the backend
serves ../frontend/dist and listens on process.env.PORT.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MAX_REQUESTS = int(os.environ.get("ARCBENCH_MAX_MODEL_REQUESTS", "28"))
MAX_TOTAL_TOKENS = int(os.environ.get("ARCBENCH_MAX_TOTAL_TOKENS", "4000000"))
MAX_SECONDS = int(os.environ.get("ARCBENCH_MAX_SECONDS", "3300"))
MAX_OUTPUT_TOKENS = 12000
REQUEST_TIMEOUT = 180

MAX_CONVERSATION_CHARS = 100_000
MAX_EXCHANGE_SUMMARY_CHARS = 900
MAX_REPAIR_AREAS = 6

UI_EXTS = {".tsx", ".ts", ".jsx", ".js", ".css", ".html"}


class Budget:
    def __init__(self) -> None:
        self.start = time.time()
        self.requests = 0
        self.tokens = 0

    def allow(self) -> bool:
        if self.requests >= MAX_REQUESTS:
            return False
        if self.tokens >= MAX_TOTAL_TOKENS:
            return False
        return (time.time() - self.start) < MAX_SECONDS

    def time_left(self) -> float:
        return MAX_SECONDS - (time.time() - self.start)

    def note(self, usage: dict) -> None:
        self.requests += 1
        if isinstance(usage, dict):
            self.tokens += int(usage.get("total_tokens") or 0)

    def status(self) -> str:
        return (
            f"requests={self.requests}/{MAX_REQUESTS} "
            f"tokens={self.tokens}/{MAX_TOTAL_TOKENS} "
            f"elapsed={int(time.time() - self.start)}s"
        )


BUDGET = Budget()


def log(msg: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def sdk_event(name: str, detail: str) -> None:
    try:
        from arcbench_agent_runtime import AgentRuntime

        runtime = AgentRuntime.from_env()
        fn = getattr(runtime.events, name, None)
        if fn:
            fn(detail)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Model client
# --------------------------------------------------------------------------


class ModelClient:
    def __init__(self) -> None:
        self.key = os.environ.get("OPENAI_API_KEY", "")
        self.base = (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
        self.model = os.environ.get("MODEL") or "deepseek-v4-flash"
        self.vbase = (os.environ.get("VISUAL_BASE_URL") or self.base).rstrip("/")
        self.vmodel = (os.environ.get("VISUAL_MODEL") or "").strip() or self.model

    def chat_messages(self, messages: list[dict], *, images: list[Path] | None = None) -> str:
        use_vision = bool(images)
        base, model = (self.vbase, self.vmodel) if use_vision else (self.base, self.model)
        sent = [dict(m) for m in messages]
        if use_vision and sent and isinstance(sent[-1].get("content"), str):
            content: list[dict] = [{"type": "text", "text": sent[-1]["content"]}]
            for img in images[:2]:
                data = base64.b64encode(img.read_bytes()).decode()
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{data}"},
                })
            sent[-1] = {"role": sent[-1]["role"], "content": content}
        body = json.dumps({
            "model": model,
            "messages": sent,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0.2,
        }).encode()
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                    payload = json.loads(resp.read())
                BUDGET.note(payload.get("usage") or {})
                choice = (payload.get("choices") or [{}])[0]
                return (choice.get("message") or {}).get("content") or ""
            except Exception as exc:
                log(f"model call error (attempt {attempt + 1}): {exc}")
                time.sleep(4 * (attempt + 1))
        return ""

    def chat(self, prompt: str, *, system: str = "",
             images: list[Path] | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat_messages(messages, images=images)


class Conversation:
    """Fixed-prefix conversation with bounded compaction.

    The system prompt and the first user message (requirement context) are never
    rewritten so the provider can reuse the request prefix. Older exchanges are
    folded into short summaries once the transcript grows too large.
    """

    def __init__(self, client: ModelClient, system: str, prefix_user: str) -> None:
        self.client = client
        self.messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prefix_user},
        ]

    def ask(self, prompt: str, *, images: list[Path] | None = None) -> str:
        self.messages.append({"role": "user", "content": prompt})
        self._compact()
        reply = self.client.chat_messages(self.messages, images=images)
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def _compact(self) -> None:
        def total() -> int:
            return sum(len(str(m.get("content") or "")) for m in self.messages)

        while total() > MAX_CONVERSATION_CHARS and len(self.messages) > 4:
            old = self.messages[2]
            summary = str(old.get("content") or "")[:MAX_EXCHANGE_SUMMARY_CHARS]
            self.messages[2:4] = [{
                "role": "user",
                "content": f"[earlier exchange condensed] {summary}",
            }]


def extract_code(text: str) -> str:
    if "```" not in text:
        return text.strip()
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)```", text, re.S)
    return max(blocks, key=len).strip() if blocks else text.strip()


def extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return {}


# --------------------------------------------------------------------------
# Requirements parsing
# --------------------------------------------------------------------------


def load_requirements(source: Path) -> tuple[dict, Path]:
    yaml_path = source
    if source.is_dir():
        candidates = [source / "requirements.yaml", source / "requirements.yml"]
        candidates += sorted(source.glob("*.yaml"))
        yaml_path = next((p for p in candidates if p.is_file()), source / "requirements.yaml")
    text = yaml_path.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:
        raise SystemExit("pyyaml is required (declared in requirements.txt)")
    return yaml.safe_load(text), yaml_path.parent


def collect_atomics(node: dict, trail: list[str], out: list[dict]) -> None:
    name = node.get("name") or node.get("id") or ""
    if node.get("type") == "ATOMIC":
        out.append({
            "id": node.get("id"),
            "name": name,
            "trail": " / ".join(trail),
            "description": node.get("description") or "",
            "scenarios": node.get("scenarios") or [],
        })
    for child in node.get("children") or []:
        collect_atomics(child, trail + [name], out)


def find_reference_images(atomics: list[dict], req_dir: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for atom in atomics:
        for rel in re.findall(r"reference/([\w./-]+\.png)", atom["description"]):
            p = req_dir / "reference" / Path(rel).name
            if not p.is_file():
                p = req_dir / rel
            if p.is_file():
                found[rel] = p
    return found


def derive_contract(atomics: list[dict]) -> dict:
    texts = [a["description"] for a in atomics]
    names: set[str] = set()
    roles: set[str] = set()
    aria: set[str] = set()
    quoted = r"[\"'\u201c\u201d\u2018\u2019]([^\"'\u201c\u201d\u2018\u2019]{1,80})[\"'\u201c\u201d\u2018\u2019]"
    for text in texts:
        for m in re.finditer(r"accessible name (?:is |of |as |is exactly )?" + quoted, text):
            names.add(m.group(1))
        for m in re.finditer(r"accessible names? \(for example, ([^)]+)\)", text):
            names.add(m.group(1).split(",")[0].strip())
        for m in re.finditer(r"(?:button|link|tab|menu item|dialog|field|input|text box|control)"
                             r"[^.\n]{0,60}?(?:named|is named|labelled|labeled) " + quoted, text):
            names.add(m.group(1))
        for m in re.finditer(r"(?:submit|action) button[^.\n]{0,40}?named " + quoted, text):
            names.add(m.group(1))
        for m in re.finditer(r"ARIA (\w+) role", text):
            roles.add(m.group(1))
        for m in re.finditer(r"(aria-[a-z]+(?:=\"[^\"]*\")?)", text):
            aria.add(m.group(1))
    names = {n for n in names if not n.startswith(("REQ", "http", "the ", "a ")) and "<" not in n[:2]}
    return {
        "accessible_names": sorted(names),
        "aria_roles": sorted(roles),
        "aria_attributes": sorted(aria),
    }


# --------------------------------------------------------------------------
# Generation stages
# --------------------------------------------------------------------------


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


BACKEND_SPEC_PROMPT = """Design the REST API for the application described below.

Return ONLY a JSON object with exactly this shape (example keys):
{
  "seed": {"<entity>": [{"<field>": <value>}]},
  "api": [{"method": "GET", "path": "/api/...", "summary": "..."}],
  "pages": [{"route": "/...", "name": "...", "summary": "..."}]
}

Requirements digest:
{reqs}

Seed data mentioned in scenarios (create records so the app works out of the box):
{scenarios}
"""

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


# --------------------------------------------------------------------------
# Project assembly
# --------------------------------------------------------------------------


def write_backend(out: Path, code: str) -> None:
    (out / "backend" / "src").mkdir(parents=True, exist_ok=True)
    (out / "backend" / "package.json").write_text(json.dumps({
        "name": "backend",
        "version": "1.0.0",
        "scripts": {"start": "node src/index.js"},
        "dependencies": {
            "express": "^4.18.2",
            "cors": "^2.8.5",
            "better-sqlite3": "^9.4.3",
        },
    }, indent=2))
    (out / "backend" / "src" / "index.js").write_text(code, encoding="utf-8")


def write_frontend(out: Path, pages: list[tuple[str, str]], design: dict) -> list[dict]:
    src = out / "frontend" / "src"
    pages_dir = src / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (out / "frontend" / "package.json").write_text(json.dumps({
        "name": "frontend",
        "version": "0.0.0",
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview",
        },
        "dependencies": {
            "react": "^19.2.0",
            "react-dom": "^19.2.0",
            "react-router-dom": "^7.11.0",
        },
        "devDependencies": {
            "@types/react": "^19.2.5",
            "@types/react-dom": "^19.2.3",
            "@vitejs/plugin-react": "^5.1.1",
            "vite": "^7.2.4",
        },
    }, indent=2))
    (out / "frontend" / "vite.config.js").write_text(
        "import { defineConfig } from 'vite'\n"
        "import react from '@vitejs/plugin-react'\n\n"
        "export default defineConfig({\n"
        "  plugins: [react()],\n"
        "  server: { proxy: { '/api': 'http://localhost:3000' } },\n"
        "})\n"
    )
    (out / "frontend" / "index.html").write_text(
        "<!DOCTYPE html>\n<html lang=\"en\">\n  <head>\n"
        "    <meta charset=\"UTF-8\" />\n"
        "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n"
        "    <title>Application</title>\n  </head>\n  <body>\n"
        "    <div id=\"root\"></div>\n"
        "    <script type=\"module\" src=\"/src/main.tsx\"></script>\n"
        "  </body>\n</html>\n"
    )
    (src / "main.tsx").write_text(
        "import React from 'react'\n"
        "import ReactDOM from 'react-dom/client'\n"
        "import { BrowserRouter } from 'react-router-dom'\n"
        "import App from './App'\n"
        "import './index.css'\n\n"
        "ReactDOM.createRoot(document.getElementById('root')!).render(\n"
        "  <React.StrictMode>\n    <BrowserRouter>\n      <App />\n    </BrowserRouter>\n  </React.StrictMode>,\n)\n"
    )
    (src / "index.css").write_text(
        "* { box-sizing: border-box; }\n"
        "body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; }\n"
        "a { color: inherit; }\n"
    )

    route_by_name = {}
    for r in design.get("pages") or []:
        if isinstance(r, dict):
            route_by_name[str(r.get("name") or "").lower()] = r.get("route") or "/"

    metas = []
    for i, (comp, code) in enumerate(pages):
        (pages_dir / f"{comp}.tsx").write_text(code, encoding="utf-8")
        route = "/"
        for name, r in route_by_name.items():
            if name and (name in comp.lower() or comp.lower() in name):
                route = r
        if i == 0:
            route = "/"
        metas.append({"comp": comp, "route": route})

    lines = []
    for comp, _ in pages:
        lines.append(f"import {comp} from './pages/{comp}'")
    lines.append("")
    lines.append("const PAGES = [")
    for m in metas:
        lines.append(f"  {{ path: '{m['route']}', element: {m['comp']} }},")
    lines.append("]")
    imports_block = "\n".join(lines)
    app_code = (
        "import { Routes, Route, Link } from 'react-router-dom'\n"
        + imports_block
        + "\n\nexport default function App() {\n"
        + "  return (\n    <div>\n"
        + "      <nav aria-label=\"Primary\" style={{ display: 'flex', gap: 16, padding: 12, borderBottom: '1px solid #ddd', flexWrap: 'wrap' }}>\n"
        + "        {PAGES.map((p: any) => (\n"
        + "          <Link key={p.path} to={p.path}>{p.path === '/' ? 'Home' : p.path}</Link>\n"
        + "        ))}\n"
        + "      </nav>\n"
        + "      <Routes>\n"
        + "        {PAGES.map((p: any) => (\n"
        + "          <Route key={p.path} path={p.path} element={p.element} />\n"
        + "        ))}\n"
        + "      </Routes>\n    </div>\n  )\n}\n"
    )
    (src / "App.tsx").write_text(app_code, encoding="utf-8")
    return metas


# --------------------------------------------------------------------------
# Build, serve, screenshot
# --------------------------------------------------------------------------


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
    code, logtxt = run_cmd(["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"], out / "backend", 600)
    notes.append(f"backend npm install exit={code}")
    code, logtxt = run_cmd(["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"], out / "frontend", 600)
    notes.append(f"frontend npm install exit={code}")
    code, logtxt = run_cmd(["npm", "run", "build"], out / "frontend", 600)
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


def screenshot_pages(out: Path, metas: list[dict], port: int, shots_dir: Path) -> dict[str, Path]:
    shots: dict[str, Path] = {}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        log(f"playwright unavailable: {exc}")
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


# --------------------------------------------------------------------------
# Failure -> module mapping and bounded repair
# --------------------------------------------------------------------------


def map_problem_to_area(problem: str, areas: list[dict], comp_of_area: dict[str, str]) -> str | None:
    """Route a failure back to the owning UI area (bounded repair scope)."""
    for area in areas:
        for rid in area.get("req_ids", []):
            if rid and rid in problem:
                return area["key"]
    tokens = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,40}", problem))
    for quoted in re.findall(r"[:\"]\s*([A-Za-z][A-Za-z0-9 _:-]{3,60})\s*$", problem, re.M):
        tokens.add(quoted.strip())
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
    corpus_by_file: dict[str, str] = {}
    for p in (out / "frontend" / "src").rglob("*"):
        if p.is_file() and p.suffix in UI_EXTS:
            corpus_by_file[str(p.relative_to(out / "frontend" / "src"))] = p.read_text(
                encoding="utf-8", errors="ignore"
            )
    joined = "\n".join(corpus_by_file.values())

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


def visual_review(client: ModelClient, reference: Path, screenshot: Path,
                  area: dict) -> dict:
    prompt = VISUAL_REVIEW_PROMPT + (
        f"\n\nThis area covers requirement ids: {', '.join(area.get('req_ids', [])[:6])}"
    )
    raw = client.chat(prompt, system=SYSTEM_PROMPT, images=[reference, screenshot])
    verdict = extract_json(raw)
    if not isinstance(verdict, dict):
        return {"ok": False, "missing_or_wrong": ["visual review returned no parseable verdict"], "controls": []}
    verdict.setdefault("ok", False)
    verdict.setdefault("missing_or_wrong", [])
    verdict.setdefault("controls", [])
    return verdict


def repair_area(client: ModelClient, out: Path, comp: str, area: dict,
                findings: list[str]) -> bool:
    """One bounded repair round for a single area, using a compacted conversation."""
    target = out / "frontend" / "src" / "pages" / f"{comp}.tsx"
    if not target.is_file():
        for cand in (out / "frontend" / "src").rglob(f"{comp}.tsx"):
            target = cand
            break
    if not target.is_file():
        return False
    source = target.read_text(encoding="utf-8", errors="ignore")

    prefix = (
        f"{SYSTEM_PROMPT}\n\nYou previously generated the React component `{comp}.tsx` "
        f"for this UI area:\n{digest_requirements(area.get('reqs', []), 6000)}\n"
        "A review found concrete problems. You will receive the current file and the "
        "problems; return the complete corrected file in one fenced code block."
    )
    conv = Conversation(client, SYSTEM_PROMPT, prefix)
    feedback = "Problems to fix:\n" + "\n".join(f"- {f}" for f in findings[:8])
    prompt = f"{feedback}\n\nCurrent file `{comp}.tsx`:\n{source[:20000]}"
    reply = conv.ask(prompt)
    updated = extract_code(reply)
    if updated and ("function" in updated or "=>" in updated) and updated != source:
        target.write_text(updated, encoding="utf-8")
        log(f"repaired {comp}.tsx ({len(findings)} findings)")
        return True
    log(f"repair produced no change for {comp}.tsx")
    return False


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: main.py <requirements_source> --output-dir <dir>")
        raise SystemExit(2)

    source = Path(sys.argv[1])
    out = Path("/workspace/template")
    for i, arg in enumerate(sys.argv):
        if arg == "--output-dir" and i + 1 < len(sys.argv):
            out = Path(sys.argv[i + 1])

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
        shot_by_comp = shots
        for area in areas:
            comp = comp_of_area.get(area["key"])
            if not comp or not area.get("images"):
                continue
            if comp not in shot_by_comp:
                continue
            if not BUDGET.allow() or BUDGET.time_left() < 120:
                break
            verdict = visual_review(client, area["images"][0], shot_by_comp[comp], area)
            status = "OK" if verdict.get("ok") else f"{len(verdict.get('missing_or_wrong', []))} diffs"
            log(f"visual review {comp}: {status} {BUDGET.status()}")
            if not verdict.get("ok"):
                findings = [str(x) for x in verdict.get("missing_or_wrong", []) if x]
                findings += [f"missing or unreachable control: {c}" for c in verdict.get("controls", []) if c]
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
        ordered = sorted(
            findings_by_area.items(),
            key=lambda kv: -len(kv[1]),
        )[:MAX_REPAIR_AREAS]
        changed = 0
        for key, findings in ordered:
            if not BUDGET.allow() or BUDGET.time_left() < 60:
                break
            comp = comp_of_area.get(key)
            area = next((a for a in areas if a["key"] == key), areas[0])
            if comp and repair_area(client, out, comp, area, findings):
                changed += 1
        log(f"repair round changed {changed} areas {BUDGET.status()}")
        if changed and BUDGET.time_left() > 180:
            ok_build, build_note = npm_install_and_build(out)
            log(f"rebuild after repair: {ok_build} ({build_note})")

    sdk_event("mark_implementation_done", f"generated {len(pages)} pages, {BUDGET.status()}")
    sdk_event("mark_run_completed", "requirement compiler finished")
    log(f"done {BUDGET.status()}")


def fallback_backend() -> str:
    return (
        "const express = require('express');\n"
        "const cors = require('cors');\n"
        "const path = require('path');\n"
        "const app = express();\n"
        "app.use(cors());\n"
        "app.use(express.json());\n"
        "app.get('/api/health', (req, res) => res.json({ status: 'ok' }));\n"
        "const dist = path.resolve(__dirname, '../../frontend/dist');\n"
        "app.use(express.static(dist));\n"
        "app.get('*', (req, res) => res.sendFile(path.join(dist, 'index.html')));\n"
        "const port = process.env.PORT || 3000;\n"
        "app.listen(port, () => console.log('listening on ' + port));\n"
    )


def fallback_home(contract: dict) -> str:
    names = contract.get("accessible_names", [])[:12]
    items = "\n".join(f"      <li>{n}</li>" for n in names)
    return (
        "export default function HomePage() {\n"
        "  return (\n    <main>\n      <h1>Home</h1>\n      <ul>\n"
        f"{items}\n"
        "      </ul>\n    </main>\n  )\n}\n"
    )


if __name__ == "__main__":
    main()
