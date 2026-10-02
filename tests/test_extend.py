from pathlib import Path

from compiler.extend import backend_covers, inspect_app
from compiler.integration import build_integration, route_table


def _fake_app(out: Path) -> None:
    (out / "backend" / "src").mkdir(parents=True, exist_ok=True)
    (out / "frontend" / "src" / "pages").mkdir(parents=True, exist_ok=True)
    (out / "backend" / "src" / "index.js").write_text(
        "const app = express();\n"
        "app.get('/api/health', (req, res) => res.json({}));\n"
        "app.post('/api/login', (req, res) => res.json({}));\n",
        encoding="utf-8",
    )
    (out / "frontend" / "src" / "App.tsx").write_text(
        "import Home from './pages/Home'\n"
        "import Login from './pages/Login'\n"
        "const PAGES = [\n"
        "  { path: '/', element: Home },\n"
        "  { path: '/login', element: Login },\n"
        "]\n",
        encoding="utf-8",
    )
    (out / "frontend" / "src" / "pages" / "Home.tsx").write_text("export default function Home(){return null}", encoding="utf-8")
    (out / "frontend" / "src" / "pages" / "Login.tsx").write_text("export default function Login(){return null}", encoding="utf-8")


def test_inspect_app_finds_api_and_pages(tmp_path: Path) -> None:
    _fake_app(tmp_path)
    info = inspect_app(tmp_path)
    assert info["has_app"] is True
    assert {"method": "GET", "path": "/api/health"} in info["api"]
    assert {"method": "POST", "path": "/api/login"} in info["api"]
    comps = {p["comp"]: p["route"] for p in info["pages"]}
    assert comps["Home"] == "/"
    assert comps["Login"] == "/login"


def test_inspect_app_empty(tmp_path: Path) -> None:
    info = inspect_app(tmp_path)
    assert info["has_app"] is False


def test_backend_covers_requires_old_endpoints() -> None:
    old = [{"method": "GET", "path": "/api/health"}]
    assert backend_covers(old, "app.get('/api/health', fn)")
    assert not backend_covers(old, "app.get('/api/other', fn)")
    assert backend_covers([], "anything")


def test_extend_mode_new_routes_avoid_root() -> None:
    areas = [
        {"key": "a.png", "reqs": [{"id": "REQ-9", "name": "NewPage", "description": "x"}],
         "req_ids": ["REQ-9"], "images": []},
    ]
    table = route_table(areas, root_taken=True)
    assert table[0]["route"] != "/"
    integration = build_integration({"api": [], "seed": {}}, areas,
                                    existing_pages=[{"comp": "Home", "route": "/"}],
                                    existing_api=[{"method": "GET", "path": "/api/health"}])
    routes = [r["route"] for r in integration["routes"]]
    assert routes[0] == "/"
    assert any(r.startswith("/") and r != "/" for r in routes[1:])
    assert integration["api"][0]["path"] == "/api/health"
