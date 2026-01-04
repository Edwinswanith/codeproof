"""Tests for Q&A service with proof-carrying answers.

Tests the complete Q&A flow:
1. Keyword extraction
2. Source retrieval
3. Answer parsing and validation
4. Confidence tier calculation
5. Citation building
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Any

from app.services.qa_service import (
    QAService,
    ConfidenceTier,
    RetrievedSource,
    AnswerSection,
    ValidatedAnswer,
    QAResult,
)


class TestKeywordExtraction:
    """Test keyword extraction from queries."""

    def test_extract_keywords_basic(self):
        """Extracts meaningful keywords from query."""
        # Create minimal mock dependencies
        db = MagicMock()
        service = QAService(db, None, None, None)

        keywords = service._extract_keywords("How does the authentication flow work?")

        assert "authentication" in keywords
        assert "flow" in keywords
        assert "work" in keywords
        # Stopwords should be filtered
        assert "how" not in keywords
        assert "does" not in keywords
        assert "the" not in keywords

    def test_extract_keywords_code_terms(self):
        """Preserves code-related terms."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        keywords = service._extract_keywords("Where is the UserController defined?")

        assert "usercontroller" in keywords
        assert "defined" in keywords

    def test_extract_keywords_empty(self):
        """Handles empty query."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        keywords = service._extract_keywords("")

        assert keywords == []

    def test_extract_keywords_only_stopwords(self):
        """Handles query with only stopwords."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        keywords = service._extract_keywords("how is the a an")

        assert keywords == []

    def test_extract_keywords_limit(self):
        """Limits keywords to 5."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        keywords = service._extract_keywords(
            "authentication authorization validation encryption hashing salting pepper"
        )

        assert len(keywords) <= 5


class TestAnswerParsing:
    """Test JSON answer parsing."""

    def test_parse_valid_json(self):
        """Parses valid JSON response."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        response = '{"sections": [{"text": "Test", "source_ids": [1]}], "unknowns": []}'
        parsed = service._parse_answer_json(response)

        assert parsed is not None
        assert len(parsed["sections"]) == 1
        assert parsed["sections"][0]["text"] == "Test"

    def test_parse_json_with_markdown(self):
        """Extracts JSON from markdown code block."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        response = '''Here is the answer:
```json
{"sections": [{"text": "Test", "source_ids": [1]}], "unknowns": []}
```
'''
        parsed = service._parse_answer_json(response)

        assert parsed is not None
        assert len(parsed["sections"]) == 1

    def test_parse_json_with_preamble(self):
        """Extracts JSON even with preamble text."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        response = '''Based on the sources, here is my analysis:
{"sections": [{"text": "The auth flow uses JWT", "source_ids": [1, 2]}], "unknowns": []}'''
        parsed = service._parse_answer_json(response)

        assert parsed is not None
        assert "JWT" in parsed["sections"][0]["text"]

    def test_parse_invalid_json(self):
        """Returns None for invalid JSON."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        response = "This is not JSON at all"
        parsed = service._parse_answer_json(response)

        assert parsed is None

    def test_parse_malformed_json(self):
        """Returns None for malformed JSON."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        response = '{"sections": [{"text": "incomplete'
        parsed = service._parse_answer_json(response)

        assert parsed is None


class TestAnswerValidation:
    """Test answer validation logic."""

    def _create_sources(self, count: int) -> list[RetrievedSource]:
        """Helper to create mock sources."""
        return [
            RetrievedSource(
                index=i + 1,
                file_path=f"app/file{i + 1}.py",
                start_line=1,
                end_line=10,
                content=f"def func{i + 1}(): pass",
                symbol_name=f"func{i + 1}",
                score=0.9 - i * 0.1,
                source_type="trigram",
            )
            for i in range(count)
        ]

    def test_validate_valid_answer(self):
        """Validates correct answer with valid sources."""
        db = MagicMock()
        service = QAService(db, None, None, None)
        sources = self._create_sources(3)

        parsed = {
            "sections": [
                {"text": "The function does X", "source_ids": [1]},
                {"text": "It also does Y", "source_ids": [2, 3]},
            ],
            "unknowns": [],
        }

        validated = service._validate_answer(parsed, sources)

        assert validated.validation_passed
        assert len(validated.sections) == 2
        assert len(validated.validation_errors) == 0

    def test_validate_invalid_source_ids(self):
        """Flags invalid source references."""
        db = MagicMock()
        service = QAService(db, None, None, None)
        sources = self._create_sources(2)  # Only sources 1 and 2

        parsed = {
            "sections": [
                {"text": "This references source 99", "source_ids": [99]},
            ],
            "unknowns": [],
        }

        validated = service._validate_answer(parsed, sources)

        # Should have validation errors but still produce result
        assert len(validated.validation_errors) > 0
        assert "99" in str(validated.validation_errors[0])

    def test_validate_removes_invalid_keeps_valid(self):
        """Keeps valid sources when some are invalid."""
        db = MagicMock()
        service = QAService(db, None, None, None)
        sources = self._create_sources(2)

        parsed = {
            "sections": [
                {"text": "Mixed sources", "source_ids": [1, 99]},
            ],
            "unknowns": [],
        }

        validated = service._validate_answer(parsed, sources)

        # Should keep section with valid source
        assert len(validated.sections) == 1
        assert validated.sections[0].source_ids == [1]

    def test_validate_empty_sections(self):
        """Handles empty sections."""
        db = MagicMock()
        service = QAService(db, None, None, None)
        sources = self._create_sources(2)

        parsed = {"sections": [], "unknowns": ["Could not find information"]}

        validated = service._validate_answer(parsed, sources)

        assert len(validated.sections) == 0
        assert len(validated.unknowns) == 1
        assert validated.confidence_tier == ConfidenceTier.NONE

    def test_validate_missing_text(self):
        """Flags sections with missing text."""
        db = MagicMock()
        service = QAService(db, None, None, None)
        sources = self._create_sources(2)

        parsed = {
            "sections": [
                {"text": "", "source_ids": [1]},  # Empty text
                {"source_ids": [2]},  # Missing text key
            ],
            "unknowns": [],
        }

        validated = service._validate_answer(parsed, sources)

        # Both sections should be filtered out
        assert len(validated.sections) == 0
        assert len(validated.validation_errors) >= 2

    def test_validate_missing_source_ids(self):
        """Flags sections with missing source_ids."""
        db = MagicMock()
        service = QAService(db, None, None, None)
        sources = self._create_sources(2)

        parsed = {
            "sections": [
                {"text": "Has no sources"},  # Missing source_ids
                {"text": "Has empty sources", "source_ids": []},
            ],
            "unknowns": [],
        }

        validated = service._validate_answer(parsed, sources)

        assert len(validated.sections) == 0
        assert len(validated.validation_errors) >= 2


class TestConfidenceTierCalculation:
    """Test confidence tier calculation."""

    def _create_sources_from_files(
        self, file_paths: list[str]
    ) -> list[RetrievedSource]:
        """Helper to create sources from specific file paths."""
        return [
            RetrievedSource(
                index=i + 1,
                file_path=path,
                start_line=1,
                end_line=10,
                content="code",
                symbol_name=f"func{i + 1}",
                score=0.9,
                source_type="trigram",
            )
            for i, path in enumerate(file_paths)
        ]

    def test_confidence_high(self):
        """HIGH: 3+ citations from 2+ files."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        sources = self._create_sources_from_files([
            "app/auth.py",
            "app/auth.py",
            "app/user.py",
        ])

        sections = [
            AnswerSection(text="Part 1", source_ids=[1, 2]),
            AnswerSection(text="Part 2", source_ids=[3]),
        ]

        tier, factors = service._calculate_confidence(sections, sources)

        assert tier == ConfidenceTier.HIGH
        assert factors["citation_count"] == 3
        assert factors["unique_files"] == 2

    def test_confidence_medium(self):
        """MEDIUM: 2 citations."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        sources = self._create_sources_from_files([
            "app/auth.py",
            "app/auth.py",
        ])

        sections = [
            AnswerSection(text="Part 1", source_ids=[1, 2]),
        ]

        tier, factors = service._calculate_confidence(sections, sources)

        assert tier == ConfidenceTier.MEDIUM
        assert factors["citation_count"] == 2

    def test_confidence_low(self):
        """LOW: 1 citation."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        sources = self._create_sources_from_files(["app/auth.py"])

        sections = [
            AnswerSection(text="Single source", source_ids=[1]),
        ]

        tier, factors = service._calculate_confidence(sections, sources)

        assert tier == ConfidenceTier.LOW
        assert factors["citation_count"] == 1

    def test_confidence_none_no_sections(self):
        """NONE: No sections."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        sources = self._create_sources_from_files(["app/auth.py"])

        tier, factors = service._calculate_confidence([], sources)

        assert tier == ConfidenceTier.NONE
        assert factors["reason"] == "no_sections"

    def test_confidence_detects_entrypoints(self):
        """Detects controller/route as entrypoints."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        sources = self._create_sources_from_files([
            "app/Http/Controllers/AuthController.php",
            "app/routes/api.php",
            "app/services/auth.py",
        ])

        sections = [
            AnswerSection(text="Controllers", source_ids=[1, 2, 3]),
        ]

        tier, factors = service._calculate_confidence(sections, sources)

        assert factors["has_entrypoints"] is True


class TestCitationBuilding:
    """Test citation building for response."""

    def test_build_citations_only_cited(self):
        """Only includes cited sources in citations."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        sources = [
            RetrievedSource(
                index=1,
                file_path="app/auth.py",
                start_line=10,
                end_line=20,
                content="def login(): pass",
                symbol_name="login",
                score=0.9,
                source_type="trigram",
            ),
            RetrievedSource(
                index=2,
                file_path="app/user.py",
                start_line=5,
                end_line=15,
                content="class User: pass",
                symbol_name="User",
                score=0.8,
                source_type="vector",
            ),
        ]

        validated = ValidatedAnswer(
            sections=[AnswerSection(text="Test", source_ids=[1])],  # Only cites source 1
            unknowns=[],
            confidence_tier=ConfidenceTier.LOW,
            confidence_factors={},
            validation_passed=True,
            validation_errors=[],
        )

        repo = MagicMock()
        repo.full_name = "owner/repo"
        repo.last_indexed_commit = "abc123"

        citations = service._build_citations(sources, validated, repo)

        # Should only include source 1
        assert len(citations) == 1
        assert citations[0]["source_index"] == 1
        assert citations[0]["file_path"] == "app/auth.py"

    def test_build_citations_github_url(self):
        """Builds correct GitHub URL."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        sources = [
            RetrievedSource(
                index=1,
                file_path="app/auth.py",
                start_line=10,
                end_line=20,
                content="code",
                symbol_name="login",
                score=0.9,
                source_type="trigram",
            ),
        ]

        validated = ValidatedAnswer(
            sections=[AnswerSection(text="Test", source_ids=[1])],
            unknowns=[],
            confidence_tier=ConfidenceTier.LOW,
            confidence_factors={},
            validation_passed=True,
            validation_errors=[],
        )

        repo = MagicMock()
        repo.full_name = "owner/repo"
        repo.last_indexed_commit = "abc123def"

        citations = service._build_citations(sources, validated, repo)

        expected_url = "https://github.com/owner/repo/blob/abc123def/app/auth.py#L10-L20"
        assert citations[0]["github_url"] == expected_url


class TestFormatAnswerText:
    """Test answer text formatting."""

    def test_format_with_citations(self):
        """Formats answer with source references."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        validated = ValidatedAnswer(
            sections=[
                AnswerSection(text="The auth flow starts here", source_ids=[1, 2]),
                AnswerSection(text="Then it goes to login", source_ids=[3]),
            ],
            unknowns=[],
            confidence_tier=ConfidenceTier.HIGH,
            confidence_factors={},
            validation_passed=True,
            validation_errors=[],
        )

        text = service._format_answer_text(validated)

        assert "The auth flow starts here [1], [2]" in text
        assert "Then it goes to login [3]" in text

    def test_format_with_unknowns(self):
        """Includes unknowns section."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        validated = ValidatedAnswer(
            sections=[
                AnswerSection(text="Found this", source_ids=[1]),
            ],
            unknowns=[
                "Could not find password reset flow",
                "Email sending not found",
            ],
            confidence_tier=ConfidenceTier.LOW,
            confidence_factors={},
            validation_passed=True,
            validation_errors=[],
        )

        text = service._format_answer_text(validated)

        assert "**Could not determine:**" in text
        assert "password reset flow" in text
        assert "Email sending" in text


class TestNoEvidenceResult:
    """Test no-evidence fallback."""

    def test_no_evidence_result(self):
        """Returns appropriate result when no evidence found."""
        db = MagicMock()
        service = QAService(db, None, None, None)

        result = service._no_evidence_result("How does auth work?")

        assert result.confidence_tier == ConfidenceTier.NONE
        assert result.has_sufficient_evidence is False
        assert len(result.citations) == 0
        assert "How does auth work?" in result.unknowns[0]
        assert "could not find" in result.answer_text.lower()


class TestRetrievedSourceMerging:
    """Test source deduplication and ranking."""

    @pytest.mark.asyncio
    async def test_sources_deduplicated(self):
        """Sources with same file:line are deduplicated."""
        db = AsyncMock()
        embedding_service = AsyncMock()
        embedding_service.llm_service = None

        service = QAService(db, embedding_service, None, None)

        # Mock trigram search returning duplicate
        with patch.object(service, "_trigram_search") as mock_trigram:
            mock_trigram.return_value = [
                {
                    "file_path": "app/auth.py",
                    "start_line": 10,
                    "end_line": 20,
                    "symbol_name": "login",
                    "score": 0.9,
                },
                {
                    "file_path": "app/auth.py",
                    "start_line": 10,  # Same location
                    "end_line": 20,
                    "symbol_name": "login",
                    "score": 0.8,
                },
            ]

            sources = await service._retrieve_sources("repo-123", "test query")

            # Should only have 1 source (deduplicated)
            assert len(sources) == 1


class TestQAServiceIntegration:
    """Integration tests with mocked dependencies."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services."""
        db = AsyncMock()
        embedding_service = AsyncMock()
        embedding_service.llm_service = None
        embedding_service.search_repo = AsyncMock(return_value=[])

        llm_service = AsyncMock()
        llm_service.model = "gpt-4"
        llm_service.generate_with_usage = AsyncMock(
            return_value=(
                '{"sections": [{"text": "Test answer", "source_ids": [1]}], "unknowns": []}',
                {"input_tokens": 100, "output_tokens": 50},
            )
        )

        github_service = AsyncMock()

        return {
            "db": db,
            "embedding_service": embedding_service,
            "llm_service": llm_service,
            "github_service": github_service,
        }

    @pytest.mark.asyncio
    async def test_no_sources_returns_no_evidence(self, mock_services):
        """Returns no evidence when no sources found."""
        service = QAService(**mock_services)

        with patch.object(service, "_trigram_search", return_value=[]):
            result = await service.answer_question(
                repo_id="repo-123",
                question="How does X work?",
                user_id="user-123",
            )

        assert result.confidence_tier == ConfidenceTier.NONE
        assert result.has_sufficient_evidence is False

    @pytest.mark.asyncio
    async def test_full_flow_with_sources(self, mock_services):
        """Full Q&A flow with mocked sources."""
        service = QAService(**mock_services)

        # Mock trigram returning results
        mock_trigram_results = [
            {
                "file_path": "app/auth.py",
                "start_line": 10,
                "end_line": 20,
                "symbol_name": "login",
                "score": 0.9,
            }
        ]

        # Mock repo
        mock_repo = MagicMock()
        mock_repo.id = "repo-123"
        mock_repo.full_name = "owner/repo"
        mock_repo.last_indexed_commit = "abc123"
        mock_repo.github_installation_id = 12345
        mock_repo.owner = "owner"
        mock_repo.name = "repo"

        with patch.object(service, "_trigram_search", return_value=mock_trigram_results):
            with patch.object(service, "_get_repo", return_value=mock_repo):
                with patch.object(service, "_fetch_snippets") as mock_fetch:
                    # Make fetch return sources with content
                    async def add_content(repo, sources):
                        for s in sources:
                            s.content = "def login(): pass"
                        return sources

                    mock_fetch.side_effect = add_content

                    with patch.object(service, "_store_answer", return_value=None):
                        result = await service.answer_question(
                            repo_id="repo-123",
                            question="How does login work?",
                            user_id="user-123",
                        )

        assert result.answer_text is not None
        assert "Test answer" in result.answer_text
        assert len(result.citations) == 1
