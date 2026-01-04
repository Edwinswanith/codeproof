"""Tests for health check endpoint."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked database."""
        with patch("app.main.init_db", new_callable=AsyncMock):
            from app.main import app
            with TestClient(app) as client:
                yield client

    def test_health_check_returns_200(self, client):
        """Health endpoint returns 200 OK."""
        response = client.get("/health")

        assert response.status_code == 200

    def test_health_check_response_body(self, client):
        """Health endpoint returns expected body."""
        response = client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_check_no_auth_required(self, client):
        """Health endpoint doesn't require authentication."""
        # No Authorization header
        response = client.get("/health")

        assert response.status_code == 200
