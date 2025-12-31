"""Repository routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.repository import Repository
from app.schemas.repository import (
    IndexStatusResponse,
    RepositoryCreate,
    RepositoryListResponse,
    RepositoryResponse,
)
from app.services.github_service import GitHubService

router = APIRouter()

github_service = GitHubService()


@router.get("", response_model=RepositoryListResponse)
async def list_repositories(
    user: CurrentUser,
    db: DbSession,
):
    """List all repositories for the current user."""
    result = await db.execute(
        select(Repository)
        .where(Repository.user_id == user.id)
        .where(Repository.deleted_at.is_(None))
        .order_by(Repository.created_at.desc())
    )
    repos = result.scalars().all()

    return RepositoryListResponse(
        repositories=[RepositoryResponse.model_validate(r) for r in repos],
        total=len(repos),
    )


@router.get("/available")
async def list_available_repos(
    user: CurrentUser,
    db: DbSession,
):
    """List repositories available to connect from GitHub installations."""
    # Get user's GitHub installations
    # Note: In production, you'd need to store the user's access token
    # For now, we'll use the installation token approach

    # This is a simplified version - in production you'd:
    # 1. Get user's installations from stored data
    # 2. List repos for each installation
    # 3. Filter out already connected repos

    return {"message": "Use GitHub App installation flow to connect repos"}


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def connect_repository(
    repo_data: RepositoryCreate,
    user: CurrentUser,
    db: DbSession,
):
    """Connect a new repository."""
    # Check if already connected
    result = await db.execute(
        select(Repository)
        .where(Repository.user_id == user.id)
        .where(Repository.github_repo_id == repo_data.github_repo_id)
        .where(Repository.deleted_at.is_(None))
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository already connected",
        )

    # Create repository
    repo = Repository(
        user_id=user.id,
        github_repo_id=repo_data.github_repo_id,
        github_installation_id=repo_data.github_installation_id,
        owner=repo_data.owner,
        name=repo_data.name,
        full_name=repo_data.full_name,
        private=repo_data.private,
        default_branch=repo_data.default_branch,
        index_status="pending",
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    return RepositoryResponse.model_validate(repo)


@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(
    repo_id: UUID,
    user: CurrentUser,
    db: DbSession,
):
    """Get a repository by ID."""
    result = await db.execute(
        select(Repository)
        .where(Repository.id == repo_id)
        .where(Repository.user_id == user.id)
        .where(Repository.deleted_at.is_(None))
    )
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    return RepositoryResponse.model_validate(repo)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repo_id: UUID,
    user: CurrentUser,
    db: DbSession,
):
    """Soft delete a repository."""
    result = await db.execute(
        select(Repository)
        .where(Repository.id == repo_id)
        .where(Repository.user_id == user.id)
        .where(Repository.deleted_at.is_(None))
    )
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    from datetime import datetime

    repo.deleted_at = datetime.utcnow()
    await db.commit()


@router.post("/{repo_id}/index", response_model=IndexStatusResponse)
async def trigger_indexing(
    repo_id: UUID,
    user: CurrentUser,
    db: DbSession,
):
    """Trigger repository indexing.

    This will:
    1. Clone the repository using ASKPASS method
    2. Parse files with tree-sitter
    3. Extract symbols and generate embeddings
    4. Store metadata (no file content)
    """
    result = await db.execute(
        select(Repository)
        .where(Repository.id == repo_id)
        .where(Repository.user_id == user.id)
        .where(Repository.deleted_at.is_(None))
    )
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    # Check if already indexing
    if repo.index_status == "indexing":
        return IndexStatusResponse(
            status="indexing",
            message="Indexing already in progress",
        )

    # Update status
    repo.index_status = "pending"
    repo.index_error = None
    await db.commit()

    # TODO: Trigger Celery task for async indexing
    # from app.tasks.index_repo import index_repository
    # index_repository.delay(str(repo.id))

    return IndexStatusResponse(
        status="pending",
        message="Indexing queued",
    )


@router.get("/{repo_id}/index/status", response_model=IndexStatusResponse)
async def get_index_status(
    repo_id: UUID,
    user: CurrentUser,
    db: DbSession,
):
    """Get the current indexing status."""
    result = await db.execute(
        select(Repository)
        .where(Repository.id == repo_id)
        .where(Repository.user_id == user.id)
        .where(Repository.deleted_at.is_(None))
    )
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    return IndexStatusResponse(
        status=repo.index_status,
        message=repo.index_error,
        file_count=repo.file_count,
        symbol_count=repo.symbol_count,
        route_count=repo.route_count,
    )
