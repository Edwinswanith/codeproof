"""Repository schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RepositoryBase(BaseModel):
    """Base repository schema."""

    owner: str
    name: str
    full_name: str
    private: bool = True
    default_branch: str = "main"


class RepositoryCreate(RepositoryBase):
    """Schema for connecting a repository."""

    github_repo_id: int
    github_installation_id: int


class RepositoryResponse(RepositoryBase):
    """Repository response schema."""

    id: UUID
    github_repo_id: int
    detected_framework: str | None
    framework_version: str | None
    index_status: str
    index_error: str | None
    last_indexed_at: datetime | None
    last_indexed_commit: str | None
    file_count: int
    symbol_count: int
    route_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class RepositoryListResponse(BaseModel):
    """List of repositories response."""

    repositories: list[RepositoryResponse]
    total: int


class IndexStatusResponse(BaseModel):
    """Index status response."""

    status: str
    progress: float | None = None
    message: str | None = None
    file_count: int = 0
    symbol_count: int = 0
    route_count: int = 0
