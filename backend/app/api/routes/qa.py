"""Q&A routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.repository import Repository
from app.services.embedding_service import EmbeddingService
from app.services.github_service import GitHubService
from app.services.llm_service import LLMService
from app.services.qa_service import QAService

router = APIRouter()


class QuestionRequest(BaseModel):
    """Question request model."""

    question: str = Field(..., min_length=1, max_length=1000)


class CitationResponse(BaseModel):
    """Citation response model."""

    source_index: int
    file_path: str
    start_line: int
    end_line: int
    snippet: str
    symbol_name: str | None
    github_url: str


class AnswerResponse(BaseModel):
    """Answer response model."""

    answer_text: str
    citations: list[CitationResponse]
    confidence_tier: str
    unknowns: list[str]
    has_sufficient_evidence: bool


@router.post("/{repo_id}/ask", response_model=AnswerResponse)
async def ask_question(
    repo_id: UUID,
    question_data: QuestionRequest,
    user: CurrentUser,
    db: DbSession,
):
    """Ask a question about the repository.

    Returns proof-carrying answer with citations.
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
    llm_service = LLMService()
    embedding_service = EmbeddingService(llm_service=llm_service)
    github_service = GitHubService()
    qa_service = QAService(db, embedding_service, llm_service, github_service)

    # Get answer
    result = await qa_service.answer_question(
        repo_id=str(repo_id),
        question=question_data.question,
        user_id=str(user.id),
    )

    # Format response
    return AnswerResponse(
        answer_text=result.answer_text,
        citations=[
            CitationResponse(
                source_index=cite["source_index"],
                file_path=cite["file_path"],
                start_line=cite["start_line"],
                end_line=cite["end_line"],
                snippet=cite["snippet"],
                symbol_name=cite.get("symbol_name"),
                github_url=cite["github_url"],
            )
            for cite in result.citations
        ],
        confidence_tier=result.confidence_tier.value,
        unknowns=result.unknowns,
        has_sufficient_evidence=result.has_sufficient_evidence,
    )

