"""Authentication service for JWT and OAuth."""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pydantic import BaseModel

from app.config import get_settings

settings = get_settings()


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # User ID
    exp: datetime
    iat: datetime


class AuthService:
    """Service for authentication operations."""

    def __init__(self):
        self.secret_key = settings.jwt_secret
        self.algorithm = settings.jwt_algorithm
        self.expiry_hours = settings.jwt_expiry_hours

    def create_jwt(self, user_id: str) -> str:
        """Create a JWT token for a user.

        Args:
            user_id: The user's UUID as string

        Returns:
            JWT token string
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(hours=self.expiry_hours)

        payload = {
            "sub": user_id,
            "iat": now,
            "exp": expire,
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_jwt(self, token: str) -> dict[str, Any] | None:
        """Verify a JWT token and return its payload.

        Args:
            token: JWT token string

        Returns:
            Token payload dict or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def refresh_jwt(self, token: str) -> str | None:
        """Refresh a JWT token if still valid.

        Args:
            token: Current JWT token

        Returns:
            New JWT token or None if current token is invalid
        """
        payload = self.verify_jwt(token)
        if not payload:
            return None

        return self.create_jwt(payload["sub"])
