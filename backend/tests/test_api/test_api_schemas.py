"""Tests for API schemas and validation."""

import pytest
from pydantic import ValidationError

from app.api.routes.qa import QuestionRequest, CitationResponse, AnswerResponse
from app.schemas.repository import RepositoryCreate, RepositoryResponse, IndexStatusResponse


class TestQuestionRequestSchema:
    """Test QuestionRequest validation."""

    def test_valid_question(self):
        """Accepts valid question."""
        request = QuestionRequest(question="How does auth work?")
        assert request.question == "How does auth work?"

    def test_rejects_empty_question(self):
        """Rejects empty question."""
        with pytest.raises(ValidationError):
            QuestionRequest(question="")

    def test_rejects_too_long_question(self):
        """Rejects question over 1000 characters."""
        with pytest.raises(ValidationError):
            QuestionRequest(question="a" * 1001)

    def test_accepts_max_length_question(self):
        """Accepts question exactly at max length."""
        request = QuestionRequest(question="a" * 1000)
        assert len(request.question) == 1000


class TestCitationResponseSchema:
    """Test CitationResponse schema."""

    def test_valid_citation(self):
        """Creates valid citation response."""
        citation = CitationResponse(
            source_index=1,
            file_path="app/auth.py",
            start_line=10,
            end_line=20,
            snippet="def login(): pass",
            symbol_name="login",
            github_url="https://github.com/owner/repo/blob/abc/app/auth.py#L10-L20"
        )

        assert citation.source_index == 1
        assert citation.file_path == "app/auth.py"
        assert citation.start_line == 10
        assert citation.github_url.startswith("https://github.com")

    def test_citation_optional_symbol_name(self):
        """Symbol name is optional."""
        citation = CitationResponse(
            source_index=1,
            file_path="app/auth.py",
            start_line=10,
            end_line=20,
            snippet="def login(): pass",
            symbol_name=None,
            github_url="https://github.com/owner/repo/blob/abc/app/auth.py#L10-L20"
        )

        assert citation.symbol_name is None


class TestAnswerResponseSchema:
    """Test AnswerResponse schema."""

    def test_valid_answer(self):
        """Creates valid answer response."""
        answer = AnswerResponse(
            answer_text="The auth flow uses JWT tokens. [1]",
            citations=[
                CitationResponse(
                    source_index=1,
                    file_path="app/auth.py",
                    start_line=10,
                    end_line=20,
                    snippet="def login(): pass",
                    symbol_name="login",
                    github_url="https://github.com/owner/repo/blob/abc/app/auth.py#L10-L20"
                )
            ],
            confidence_tier="high",
            unknowns=[],
            has_sufficient_evidence=True
        )

        assert answer.confidence_tier == "high"
        assert len(answer.citations) == 1
        assert answer.has_sufficient_evidence is True

    def test_answer_with_unknowns(self):
        """Answer can include unknowns."""
        answer = AnswerResponse(
            answer_text="Partial answer",
            citations=[],
            confidence_tier="none",
            unknowns=["Could not find X", "Could not find Y"],
            has_sufficient_evidence=False
        )

        assert len(answer.unknowns) == 2
        assert answer.has_sufficient_evidence is False


class TestRepositoryCreateSchema:
    """Test RepositoryCreate schema."""

    def test_valid_repo_create(self):
        """Creates valid repository."""
        repo = RepositoryCreate(
            github_repo_id=12345,
            github_installation_id=67890,
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            private=True,
            default_branch="main"
        )

        assert repo.github_repo_id == 12345
        assert repo.full_name == "testowner/testrepo"

    def test_repo_defaults(self):
        """Uses default values."""
        repo = RepositoryCreate(
            github_repo_id=12345,
            github_installation_id=67890,
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo"
        )

        assert repo.private is True
        assert repo.default_branch == "main"


class TestIndexStatusResponseSchema:
    """Test IndexStatusResponse schema."""

    def test_valid_status(self):
        """Creates valid status response."""
        status = IndexStatusResponse(
            status="ready",
            message=None,
            file_count=50,
            symbol_count=200,
            route_count=10
        )

        assert status.status == "ready"
        assert status.file_count == 50

    def test_status_defaults(self):
        """Uses default values."""
        status = IndexStatusResponse(status="pending")

        assert status.file_count == 0
        assert status.symbol_count == 0
        assert status.progress is None
