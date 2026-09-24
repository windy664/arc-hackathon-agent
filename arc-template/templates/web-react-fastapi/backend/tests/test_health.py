from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_modules_endpoint_has_seed_module() -> None:
    response = TestClient(app).get("/api/modules")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "home"

