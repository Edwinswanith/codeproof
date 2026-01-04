"""Tests for authentication service."""

import pytest
import jwt
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock


class TestAuthService:
    """Test AuthService JWT functionality."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService with mocked settings."""
        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret-key-that-is-long-enough"
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.jwt_expiry_hours = 24

            from app.services.auth_service import AuthService
            return AuthService()

    def test_create_jwt_returns_token(self, auth_service):
        """create_jwt returns a JWT token string."""
        user_id = "user-123"
        token = auth_service.create_jwt(user_id)

        assert isinstance(token, str)
        assert len(token) > 0
        # JWT format: header.payload.signature
        assert token.count(".") == 2

    def test_create_jwt_contains_user_id(self, auth_service):
        """create_jwt includes user_id in payload."""
        user_id = "user-456"
        token = auth_service.create_jwt(user_id)

        # Decode without verification to check payload
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["sub"] == user_id

    def test_create_jwt_includes_expiration(self, auth_service):
        """create_jwt includes expiration time."""
        token = auth_service.create_jwt("user-789")

        payload = jwt.decode(token, options={"verify_signature": False})
        assert "exp" in payload
        assert "iat" in payload

        # exp should be after iat
        assert payload["exp"] > payload["iat"]

    def test_verify_jwt_valid_token(self, auth_service):
        """verify_jwt returns payload for valid token."""
        user_id = "user-abc"
        token = auth_service.create_jwt(user_id)

        payload = auth_service.verify_jwt(token)

        assert payload is not None
        assert payload["sub"] == user_id

    def test_verify_jwt_invalid_token(self, auth_service):
        """verify_jwt returns None for invalid token."""
        result = auth_service.verify_jwt("invalid-token")
        assert result is None

    def test_verify_jwt_expired_token(self, auth_service):
        """verify_jwt returns None for expired token."""
        # Create expired token manually
        expired_payload = {
            "sub": "user-expired",
            "iat": datetime.now(timezone.utc) - timedelta(hours=48),
            "exp": datetime.now(timezone.utc) - timedelta(hours=24),
        }
        expired_token = jwt.encode(
            expired_payload,
            auth_service.secret_key,
            algorithm=auth_service.algorithm
        )

        result = auth_service.verify_jwt(expired_token)
        assert result is None

    def test_verify_jwt_wrong_signature(self, auth_service):
        """verify_jwt returns None for token with wrong signature."""
        # Create token with different secret
        wrong_payload = {
            "sub": "user-wrong",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        }
        wrong_token = jwt.encode(
            wrong_payload,
            "wrong-secret-key",
            algorithm="HS256"
        )

        result = auth_service.verify_jwt(wrong_token)
        assert result is None

    def test_refresh_jwt_valid_token(self, auth_service):
        """refresh_jwt returns new token for valid token."""
        user_id = "user-refresh"
        original_token = auth_service.create_jwt(user_id)

        new_token = auth_service.refresh_jwt(original_token)

        assert new_token is not None
        # New token should be a valid JWT (may be same if called within same second)
        assert isinstance(new_token, str)
        assert new_token.count(".") == 2

        # Verify new token is valid and contains same user
        payload = auth_service.verify_jwt(new_token)
        assert payload["sub"] == user_id

    def test_refresh_jwt_invalid_token(self, auth_service):
        """refresh_jwt returns None for invalid token."""
        result = auth_service.refresh_jwt("invalid-token")
        assert result is None

    def test_refresh_jwt_expired_token(self, auth_service):
        """refresh_jwt returns None for expired token."""
        # Create expired token
        expired_payload = {
            "sub": "user-expired",
            "iat": datetime.now(timezone.utc) - timedelta(hours=48),
            "exp": datetime.now(timezone.utc) - timedelta(hours=24),
        }
        expired_token = jwt.encode(
            expired_payload,
            auth_service.secret_key,
            algorithm=auth_service.algorithm
        )

        result = auth_service.refresh_jwt(expired_token)
        assert result is None


class TestTokenPayload:
    """Test TokenPayload Pydantic model."""

    def test_token_payload_creation(self):
        """TokenPayload can be created with valid data."""
        from app.services.auth_service import TokenPayload

        now = datetime.now(timezone.utc)
        payload = TokenPayload(
            sub="user-123",
            exp=now + timedelta(hours=24),
            iat=now,
        )

        assert payload.sub == "user-123"
        assert payload.exp > payload.iat
