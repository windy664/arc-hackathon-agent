"""Write the deliverable backend/ and frontend/ trees into the output directory."""

from __future__ import annotations

import json
from pathlib import Path


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
