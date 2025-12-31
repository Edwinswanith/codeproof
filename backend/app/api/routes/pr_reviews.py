"""PR review routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.pr_finding import PRFinding
from app.models.pr_review import PRReview
from app.models.repository import Repository
from app.services.github_service import GitHubService
from app.services.llm_service import LLMService
from app.services.review_service import ReviewService

router = APIRouter()


class PRReviewRequest(BaseModel):
    """PR review request model."""

    pr_number: int = Field(..., gt=0)


class FindingResponse(BaseModel):
    """PR finding response model."""

    id: UUID
    severity: str
    category: str
    file_path: str
    start_line: int | None
    end_line: int | None
    evidence: dict
    explanation: str | None
    suggested_fix: str | None
    status: str


class PRReviewResponse(BaseModel):
    """PR review response model."""

    id: UUID
    pr_number: int
    pr_title: str | None
    pr_url: str | None
    status: str
    files_changed: int
    findings_count: int
    critical_count: int
    findings: list[FindingResponse]


@router.post("/{repo_id}/review", response_model=PRReviewResponse)
async def trigger_pr_review(
    repo_id: UUID,
    review_data: PRReviewRequest,
    user: CurrentUser,
    db: DbSession,
):
    """Trigger a PR review.

    Analyzes the PR using high-precision analyzers and posts findings to GitHub.
    """
    # Get repository
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

    # Check if indexed
    if repo.index_status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository not indexed yet. Please wait for indexing to complete.",
        )

    # Initialize services
    github_service = GitHubService()
    llm_service = LLMService()
    review_service = ReviewService(db, github_service, llm_service)

    # Perform review
    review = await review_service.review_pr(
        repo_id=str(repo_id),
        pr_number=review_data.pr_number,
        installation_id=repo.github_installation_id,
    )

    # Get findings
    findings_result = await db.execute(
        select(PRFinding).where(PRFinding.pr_review_id == review.id)
    )
    findings = findings_result.scalars().all()

    return PRReviewResponse(
        id=review.id,
        pr_number=review.pr_number,
        pr_title=review.pr_title,
        pr_url=review.pr_url,
        status=review.status,
        files_changed=review.files_changed,
        findings_count=review.findings_count,
        critical_count=review.critical_count,
        findings=[
            FindingResponse(
                id=f.id,
                severity=f.severity,
                category=f.category,
                file_path=f.file_path,
                start_line=f.start_line,
                end_line=f.end_line,
                evidence=f.evidence,
                explanation=f.explanation,
                suggested_fix=f.suggested_fix,
                status=f.status,
            )
            for f in findings
        ],
    )


@router.get("/{repo_id}/reviews/{pr_number}", response_model=PRReviewResponse)
async def get_pr_review(
    repo_id: UUID,
    pr_number: int,
    user: CurrentUser,
    db: DbSession,
):
    """Get PR review by PR number."""
    # Get repository
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

    # Get review
    review_result = await db.execute(
        select(PRReview)
        .where(PRReview.repo_id == repo_id)
        .where(PRReview.pr_number == pr_number)
    )
    review = review_result.scalar_one_or_none()

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PR review not found",
        )

    # Get findings
    findings_result = await db.execute(
        select(PRFinding).where(PRFinding.pr_review_id == review.id)
    )
    findings = findings_result.scalars().all()

    return PRReviewResponse(
        id=review.id,
        pr_number=review.pr_number,
        pr_title=review.pr_title,
        pr_url=review.pr_url,
        status=review.status,
        files_changed=review.files_changed,
        findings_count=review.findings_count,
        critical_count=review.critical_count,
        findings=[
            FindingResponse(
                id=f.id,
                severity=f.severity,
                category=f.category,
                file_path=f.file_path,
                start_line=f.start_line,
                end_line=f.end_line,
                evidence=f.evidence,
                explanation=f.explanation,
                suggested_fix=f.suggested_fix,
                status=f.status,
            )
            for f in findings
        ],
    )

