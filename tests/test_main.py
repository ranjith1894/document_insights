import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthCheck:
    def test_health_check_all_ok(self, client):
        with patch("app.routers.health.db") as mock_db:
            with patch("app.routers.health.redis_client") as mock_redis:
                mock_db.command = AsyncMock()
                mock_redis.ping = AsyncMock()

                response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["mongodb"] is True
        assert data["redis"] is True

    def test_health_check_mongodb_down(self, client):
        with patch("app.routers.health.db") as mock_db:
            with patch("app.routers.health.redis_client") as mock_redis:
                mock_db.command = AsyncMock(side_effect=Exception("Connection failed"))
                mock_redis.ping = AsyncMock()

                response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["mongodb"] is False
        assert data["redis"] is True

    def test_health_check_redis_down(self, client):
        with patch("app.routers.health.db") as mock_db:
            with patch("app.routers.health.redis_client") as mock_redis:
                mock_db.command = AsyncMock()
                mock_redis.ping = AsyncMock(side_effect=Exception("Connection failed"))

                response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["mongodb"] is True
        assert data["redis"] is False

    def test_health_check_both_down(self, client):
        with patch("app.routers.health.db") as mock_db:
            with patch("app.routers.health.redis_client") as mock_redis:
                mock_db.command = AsyncMock(side_effect=Exception("Connection failed"))
                mock_redis.ping = AsyncMock(side_effect=Exception("Connection failed"))

                response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["mongodb"] is False
        assert data["redis"] is False
