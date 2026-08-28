from fastapi.testclient import TestClient

from okapi_api.main import app


def test_health_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_lists_v1_routers() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    # Routers are registered even though no routes are implemented yet; the schema
    # should at least load without error.
    assert isinstance(paths, dict)
