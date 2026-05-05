from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_reports_healthy() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "restaurant-menu-importer-api",
        "environment": "development",
    }
