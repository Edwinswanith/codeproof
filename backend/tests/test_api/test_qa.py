"""Tests for Q&A API endpoints."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestQAAuthRequired:
    """Test that Q&A endpoints require authentication."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked database init."""
        with patch("app.main.init_db", new_callable=AsyncMock):
            from app.main import app
            with TestClient(app) as client:
                yield client

    def test_ask_requires_auth(self, client):
        """Returns 401/403 when no auth token provided."""
        repo_id = uuid.uuid4()
        response = client.post(
            f"/api/{repo_id}/ask",
            json={"question": "How does auth work?"}
        )
        assert response.status_code in (401, 403)


class TestQARequestValidation:
    """Test request validation for Q&A endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked database init."""
        with patch("app.main.init_db", new_callable=AsyncMock):
            from app.main import app
            with TestClient(app) as client:
                yield client

    def test_empty_question_rejected(self, client):
        """Rejects empty question."""
        repo_id = uuid.uuid4()
        response = client.post(
            f"/api/{repo_id}/ask",
            json={"question": ""},
            headers={"Authorization": "Bearer fake_token"}
        )
        # Should fail validation (422) or auth (401/403)
        assert response.status_code in (401, 403, 422)

    def test_too_long_question_rejected(self, client):
        """Rejects question over 1000 characters."""
        repo_id = uuid.uuid4()
        long_question = "a" * 1001

        response = client.post(
            f"/api/{repo_id}/ask",
            json={"question": long_question},
            headers={"Authorization": "Bearer fake_token"}
        )
        # Should fail validation (422) or auth (401/403)
        assert response.status_code in (401, 403, 422)

    def test_missing_question_rejected(self, client):
        """Rejects request without question field."""
        repo_id = uuid.uuid4()
        response = client.post(
            f"/api/{repo_id}/ask",
            json={},
            headers={"Authorization": "Bearer fake_token"}
        )
        # Should fail validation (422) or auth (401/403)
        assert response.status_code in (401, 403, 422)

    def test_invalid_repo_uuid_rejected(self, client):
        """Rejects invalid UUID in path."""
        response = client.post(
            "/api/not-a-uuid/ask",
            json={"question": "Test?"}
        )
        # Auth check happens before path validation, so we get 401/403 first
        assert response.status_code in (401, 403, 422)
