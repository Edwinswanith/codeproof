"""User schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema."""

    github_login: str
    email: EmailStr | None = None
    avatar_url: str | None = None


class UserCreate(UserBase):
    """Schema for creating a user."""

    github_id: int


class UserResponse(UserBase):
    """User response schema."""

    id: UUID
    github_id: int
    plan: str
    questions_used_this_month: int
    pr_reviews_used_this_month: int
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
