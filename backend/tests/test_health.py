"""Проверка каркаса приложения."""
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_swagger_is_available():
    client = TestClient(create_app())
    assert client.get("/openapi.json").status_code == 200
