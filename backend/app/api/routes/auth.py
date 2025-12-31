"""Authentication routes."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession
from app.models.user import User
from app.schemas.user import TokenResponse, UserResponse
from app.services.auth_service import AuthService
from app.services.github_service import GitHubService

router = APIRouter()

# Services
github_service = GitHubService()
auth_service = AuthService()

# In-memory state storage (use Redis in production)
_oauth_states: dict[str, bool] = {}


@router.get("/github")
async def github_oauth_redirect(response: Response):
    """Redirect to GitHub OAuth authorization page."""
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = True

    oauth_url = github_service.get_oauth_url(state)
    response.status_code = status.HTTP_302_FOUND
    response.headers["Location"] = oauth_url
    return {"redirect_url": oauth_url}


@router.get("/callback", response_model=TokenResponse)
async def github_oauth_callback(
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    db: DbSession,
):
    """Handle GitHub OAuth callback.

    Exchanges code for token, creates/updates user, returns JWT.
    """
    # Verify state
    if state not in _oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )
    del _oauth_states[state]

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

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth failed: {str(e)}",
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
