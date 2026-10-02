from compiler.integration import (
    build_integration,
    comp_name_for,
    digest_integration,
    route_table,
    area_scenario_digest,
)


def _areas(n: int) -> list[dict]:
    return [
        {"key": f"img-{i}.png",
         "reqs": [{"id": f"REQ-{i}", "name": f"Page{i}", "description": "x",
                   "scenarios": [{"name": "s", "steps": [
                       {"keyword": "GIVEN", "content": "seeded workbook `Q3 Sales`"},
                       {"keyword": "WHEN", "content": "user clicks"},
                       {"keyword": "THEN", "content": "visible"},
                   ]}]}],
         "req_ids": [f"REQ-{i}"], "images": []}
        for i in range(n)
    ]


def test_route_table_first_area_owns_root() -> None:
    table = route_table(_areas(3))
    assert table[0]["route"] == "/"
    assert table[1]["route"].startswith("/")
    assert table[1]["route"] != "/"
    assert [t["comp"] for t in table] == ["Page0", "Page1", "Page2"]


def test_integration_digest_contains_api_routes_seed() -> None:
    design = {
        "api": [{"method": "GET", "path": "/api/items", "summary": "list"}],
        "seed": {"workbooks": [{"name": "Q3 Sales"}]},
        "pages": [],
    }
    integration = build_integration(design, _areas(2))
    text = digest_integration(integration)
    assert "/api/items" in text
    assert "Q3 Sales" in text
    assert "TEAM INTEGRATION CONTRACT" in text
    assert "Page0" in text or "/" in text


def test_area_scenario_digest_carries_seed_values() -> None:
    text = area_scenario_digest(_areas(1)[0])
    assert "Q3 Sales" in text
    assert "GIVEN" in text


def test_comp_name_matches_assembly_mapping() -> None:
    areas = _areas(2)
    table = route_table(areas)
    assert all(t["comp"] == comp_name_for(a) for t, a in zip(table, areas))
