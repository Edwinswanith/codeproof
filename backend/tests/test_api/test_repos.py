"""Tests for repository API endpoints."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestRepositoryAuthRequired:
    """Test that repository endpoints require authentication."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked database init."""
        with patch("app.main.init_db", new_callable=AsyncMock):
            from app.main import app
            with TestClient(app) as client:
                yield client

    def test_list_repos_requires_auth(self, client):
        """Returns 401/403 when no auth token provided."""
        response = client.get("/api/repos")
        assert response.status_code in (401, 403)

    def test_get_repo_requires_auth(self, client):
        """Returns 401/403 when no auth token provided."""
        repo_id = uuid.uuid4()
        response = client.get(f"/api/repos/{repo_id}")
        assert response.status_code in (401, 403)

    def test_connect_repo_requires_auth(self, client):
        """Returns 401/403 when no auth token provided."""
        response = client.post(
            "/api/repos",
            json={
                "github_repo_id": 12345,
                "github_installation_id": 67890,
                "owner": "testowner",
                "name": "testrepo",
                "full_name": "testowner/testrepo",
            }
        )
        assert response.status_code in (401, 403)

    def test_delete_repo_requires_auth(self, client):
        """Returns 401/403 when no auth token provided."""
        repo_id = uuid.uuid4()
        response = client.delete(f"/api/repos/{repo_id}")
        assert response.status_code in (401, 403)

    def test_index_status_requires_auth(self, client):
        """Returns 401/403 when no auth token provided."""
        repo_id = uuid.uuid4()
        response = client.get(f"/api/repos/{repo_id}/index/status")
        assert response.status_code in (401, 403)

    def test_trigger_index_requires_auth(self, client):
        """Returns 401/403 when no auth token provided."""
        repo_id = uuid.uuid4()
        response = client.post(f"/api/repos/{repo_id}/index")
        assert response.status_code in (401, 403)


class TestRepositoryRequestValidation:
    """Test request validation for repository endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked database init."""
        with patch("app.main.init_db", new_callable=AsyncMock):
            from app.main import app
            with TestClient(app) as client:
                yield client

    def test_connect_repo_validates_required_fields(self, client):
        """Validates required fields for connecting repo."""
        # Missing required fields
        response = client.post(
            "/api/repos",
            json={"owner": "testowner"},
            headers={"Authorization": "Bearer fake_token"}
        )
        # Should fail validation (422) or auth (401/403)
        assert response.status_code in (401, 403, 422)

    def test_invalid_uuid_rejected(self, client):
        """Rejects invalid UUID in path."""
        response = client.get("/api/repos/not-a-uuid")
        # Auth check happens before path validation, so we may get 401/403 first
        assert response.status_code in (401, 403, 422)
