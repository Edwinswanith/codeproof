"""Authentication routes."""

import logging
import secrets
from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession
from app.config import get_settings
from app.models.user import User
from app.schemas.user import TokenResponse, UserResponse
from app.services.auth_service import AuthService
from app.services.github_service import GitHubService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# Services
github_service = GitHubService()
auth_service = AuthService()

# Redis client for OAuth state (lazy initialized)
_redis_client: redis.Redis | None = None
_OAUTH_STATE_TTL_SECONDS = 600  # 10 minutes
_OAUTH_STATE_PREFIX = "oauth_state:"


async def _get_redis() -> redis.Redis:
    """Get or create Redis client for OAuth state storage."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def _add_oauth_state(state: str) -> bool:
    """Add OAuth state with TTL in Redis. Returns False on failure."""
    try:
        client = await _get_redis()
        key = f"{_OAUTH_STATE_PREFIX}{state}"
        # SET with NX (only if not exists) and EX (expiry)
        result = await client.set(key, "1", ex=_OAUTH_STATE_TTL_SECONDS, nx=True)
        return result is not None
    except redis.RedisError as e:
        logger.error(f"Redis error adding OAuth state: {e}")
        return False


async def _verify_oauth_state(state: str) -> bool:
    """Verify and consume OAuth state from Redis. Returns False if invalid or expired."""
    try:
        client = await _get_redis()
        key = f"{_OAUTH_STATE_PREFIX}{state}"
        # GETDEL atomically gets and deletes - prevents replay attacks
        result = await client.getdel(key)
        return result is not None
    except redis.RedisError as e:
        logger.error(f"Redis error verifying OAuth state: {e}")
        return False


@router.get("/github")
async def github_oauth_redirect(response: Response):
    """Redirect to GitHub OAuth authorization page."""
    state = secrets.token_urlsafe(32)

    if not await _add_oauth_state(state):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again.",
        )

    oauth_url = github_service.get_oauth_url(state)
    response.status_code = status.HTTP_302_FOUND
    response.headers["Location"] = oauth_url
    return {"redirect_url": oauth_url}


@router.get("/callback", response_model=TokenResponse)
async def github_oauth_callback(
    code: Annotated[str, Query(min_length=1, max_length=256)],
    state: Annotated[str, Query(min_length=1, max_length=256)],
    db: DbSession,
):
    """Handle GitHub OAuth callback.

    Exchanges code for token, creates/updates user, returns JWT.
    """
    # Verify state (also handles expiry and consumption)
    if not await _verify_oauth_state(state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state. Please try again.",
        )

    try:
        # Exchange code for token
        access_token = await github_service.exchange_code(code)

        # Get user info
        github_user = await github_service.get_user(access_token)

        # Find or create user
        result = await db.execute(
            select(User).where(User.github_id == github_user.id)
        )
        user = result.scalar_one_or_none()

        if user:
            # Update existing user
            user.github_login = github_user.login
            user.email = github_user.email
            user.avatar_url = github_user.avatar_url
        else:
            # Create new user
            user = User(
                github_id=github_user.id,
                github_login=github_user.login,
                email=github_user.email,
                avatar_url=github_user.avatar_url,
            )
            db.add(user)

        await db.commit()
        await db.refresh(user)

        # Generate JWT
        jwt_token = auth_service.create_jwt(str(user.id))

        return TokenResponse(
            access_token=jwt_token,
            user=UserResponse.model_validate(user),
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        # Log the actual error for debugging, but don't expose to client
        logger.exception("OAuth callback failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication failed. Please try again.",
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token: str,
    db: DbSession,
):
    """Refresh an existing JWT token."""
    new_token = auth_service.refresh_jwt(token)
    if not new_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    payload = auth_service.verify_jwt(new_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    result = await db.execute(
        select(User).where(User.id == payload["sub"])
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return TokenResponse(
        access_token=new_token,
        user=UserResponse.model_validate(user),
    )
