"""Q&A service with proof-carrying answers."""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer import Answer
from app.models.citation import Citation
from app.models.repository import Repository
from app.models.snippet_cache import SnippetCache

logger = logging.getLogger(__name__)


class ConfidenceTier(str, Enum):
    """Confidence tier for answers."""

    HIGH = "high"  # >= 3 citations from >= 2 files
    MEDIUM = "medium"  # >= 2 citations
    LOW = "low"  # 1 citation
    NONE = "none"  # 0 citations or validation failed


@dataclass
class RetrievedSource:
    """A source retrieved from search."""

    index: int
    file_path: str
    start_line: int
    end_line: int
    content: str
    symbol_name: str | None
    score: float
    source_type: str  # 'trigram' or 'vector'


@dataclass
class AnswerSection:
    """A section of the answer with its sources."""

    text: str
    source_ids: list[int]


@dataclass
class ValidatedAnswer:
    """A fully validated answer."""

    sections: list[AnswerSection]
    unknowns: list[str]
    confidence_tier: ConfidenceTier
    confidence_factors: dict[str, Any]
    validation_passed: bool
    validation_errors: list[str]


@dataclass
class QAResult:
    """Final Q&A result returned to user."""

    answer_text: str
    citations: list[dict[str, Any]]
    confidence_tier: ConfidenceTier
    unknowns: list[str]
    has_sufficient_evidence: bool


class QAService:
    """Q&A service with proof-carrying answers."""

    ANSWER_PROMPT = """You are a code analysis assistant. Answer the question based ONLY on the provided sources.

CRITICAL RULES:
1. You MUST output valid JSON matching the schema below
2. Every claim MUST reference at least one source_id
3. If you cannot answer part of the question, put it in "unknowns"
4. Do NOT invent file paths or line numbers
5. Do NOT make claims without source evidence

OUTPUT SCHEMA:
{{
    "sections": [
        {{"text": "The authentication flow starts in...", "source_ids": [1, 3]}},
        {{"text": "Passwords are hashed using bcrypt...", "source_ids": [2]}}
    ],
    "unknowns": [
        "I could not find where password reset emails are sent"
    ]
}}

SOURCES:
{{sources}}

QUESTION: {{question}}

Respond with ONLY the JSON object, no other text:"""

    def __init__(
        self,
        db: AsyncSession,
        embedding_service,
        llm_service,
        github_service,
    ):
        self.db = db
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.github_service = github_service

    async def answer_question(
        self,
        repo_id: str,
        question: str,
        user_id: str,
    ) -> QAResult:
        """Answer a question with validated citations.

        Args:
            repo_id: Repository UUID
            question: User question
            user_id: User UUID

        Returns:
            QAResult with answer and citations
        """
        # Step 1: Retrieve sources
        sources = await self._retrieve_sources(repo_id, question)

        # Step 2: Check minimum sources
        if len(sources) < 1:
            return self._no_evidence_result(question)

        # Step 3: Fetch actual snippets from GitHub
        repo = await self._get_repo(repo_id)
        sources = await self._fetch_snippets(repo, sources)

        # Step 4: Generate answer with structured output
        validated, usage = await self._generate_validated_answer(question, sources)

        # Step 5: Build citations
        citations = self._build_citations(sources, validated, repo)

        # Step 6: Store answer
        await self._store_answer(repo_id, user_id, question, validated, citations, usage)

        return QAResult(
            answer_text=self._format_answer_text(validated),
            citations=citations,
            confidence_tier=validated.confidence_tier,
            unknowns=validated.unknowns,
            has_sufficient_evidence=validated.confidence_tier != ConfidenceTier.NONE,
        )

    async def _retrieve_sources(
        self,
        repo_id: str,
        question: str,
    ) -> list[RetrievedSource]:
        """Retrieve sources using hybrid search."""
        sources = []
        seen_keys = set()
        index = 0

        # Trigram search on symbols
        trigram_results = await self._trigram_search(repo_id, question)
        for r in trigram_results:
            key = f"{r['file_path']}:{r['start_line']}"
            if key not in seen_keys:
                seen_keys.add(key)
                index += 1
                sources.append(
                    RetrievedSource(
                        index=index,
                        file_path=r["file_path"],
                        start_line=r["start_line"],
                        end_line=r["end_line"],
                        content="",  # Fetched later from GitHub
                        symbol_name=r.get("symbol_name"),
                        score=r["score"],
                        source_type="trigram",
                    )
                )

        # Vector search (requires LLM service in embedding service)
        if self.llm_service:
            # Set LLM service in embedding service if not already set
            if not self.embedding_service.llm_service:
                self.embedding_service.llm_service = self.llm_service

            vector_results = await self.embedding_service.search(repo_id, question, limit=15)
            for r in vector_results:
                key = f"{r['file_path']}:{r['start_line']}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    index += 1
                    sources.append(
                        RetrievedSource(
                            index=index,
                            file_path=r["file_path"],
                            start_line=r["start_line"],
                            end_line=r["end_line"],
                            content="",
                            symbol_name=r.get("symbol_name"),
                            score=r["score"],
                            source_type="vector",
                        )
                    )

        # Sort by score and limit
        sources.sort(key=lambda x: x.score, reverse=True)

        # Re-index after sorting
        for i, source in enumerate(sources[:15], 1):
            source.index = i

        return sources[:15]

    async def _trigram_search(
        self,
        repo_id: str,
        query: str,
    ) -> list[dict[str, Any]]:
        """Search using trigram similarity."""
        from app.models.symbol import Symbol

        # Extract keywords from query
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        # Build trigram query
        sql = text("""
            SELECT 
                s.name,
                s.qualified_name,
                s.file_path,
                s.start_line,
                s.end_line,
                s.signature,
                GREATEST(
                    similarity(s.name, :query),
                    similarity(s.qualified_name, :query)
                ) as score
            FROM symbols s
            WHERE s.repo_id = :repo_id
            AND (
                s.name % :query
                OR s.qualified_name % :query
                OR s.search_text ILIKE :like_query
            )
            ORDER BY score DESC
            LIMIT 10
        """)

        result = await self.db.execute(
            sql,
            {
                "repo_id": repo_id,
                "query": " ".join(keywords),
                "like_query": f"%{keywords[0]}%" if keywords else "%",
            },
        )

        return [
            {
                "file_path": r.file_path,
                "start_line": r.start_line,
                "end_line": r.end_line,
                "symbol_name": r.qualified_name,
                "score": float(r.score) if r.score else 0.5,
            }
            for r in result
        ]

    def _extract_keywords(self, query: str) -> list[str]:
        """Extract meaningful keywords from query."""
        # Remove common words
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "how",
            "what",
            "where",
            "when",
            "why",
            "which",
            "who",
            "does",
            "do",
            "did",
            "has",
            "have",
            "had",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }

        words = re.findall(r"\b\w+\b", query.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]

        return keywords[:5]

    async def _fetch_snippets(
        self,
        repo: Repository,
        sources: list[RetrievedSource],
    ) -> list[RetrievedSource]:
        """Fetch actual code snippets from GitHub."""
        if not repo.last_indexed_commit:
            return sources

        for source in sources:
            # Check cache first
            cached = await self._get_cached_snippet(
                repo.id,
                repo.last_indexed_commit,
                source.file_path,
                source.start_line,
                source.end_line,
            )

            if cached:
                source.content = cached
                continue

            # Fetch from GitHub
            try:
                content = await self.github_service.get_file_content(
                    installation_id=repo.github_installation_id,
                    owner=repo.owner,
                    repo=repo.name,
                    path=source.file_path,
                    ref=repo.last_indexed_commit,
                )

                # Extract lines
                lines = content.split("\n")
                start_idx = max(0, source.start_line - 1)
                end_idx = min(len(lines), source.end_line)
                snippet = "\n".join(lines[start_idx:end_idx])

                # Limit size
                if len(snippet) > 500:
                    snippet = snippet[:500] + "..."

                source.content = snippet

                # Cache it
                await self._cache_snippet(
                    repo.id,
                    repo.last_indexed_commit,
                    source.file_path,
                    source.start_line,
                    source.end_line,
                    snippet,
                )

            except Exception as e:
                logger.warning(f"Failed to fetch snippet: {e}")
                source.content = f"[Could not fetch: {str(e)}]"

        return sources

    async def _generate_validated_answer(
        self,
        question: str,
        sources: list[RetrievedSource],
    ) -> tuple[ValidatedAnswer, dict[str, int]]:
        """Generate answer and validate it.

        Returns:
            Tuple of (ValidatedAnswer, usage_dict)
        """
        # Build sources text
        sources_text = "\n\n".join(
            [
                f"[Source {s.index}] {s.file_path}:{s.start_line}-{s.end_line}"
                f"{f' ({s.symbol_name})' if s.symbol_name else ''}\n"
                f"```\n{s.content}\n```"
                for s in sources
            ]
        )

        prompt = self.ANSWER_PROMPT.format(sources=sources_text, question=question)

        # Generate with usage tracking
        response, usage = await self.llm_service.generate_with_usage(prompt, max_tokens=1500)

        # Parse JSON
        parsed = self._parse_answer_json(response)
        if not parsed:
            # Retry once
            response, retry_usage = await self.llm_service.generate_with_usage(
                prompt + "\n\nRemember: Output ONLY valid JSON.",
                max_tokens=1500,
            )
            usage = retry_usage
            parsed = self._parse_answer_json(response)

        if not parsed:
            return (
                ValidatedAnswer(
                    sections=[],
                    unknowns=["Failed to generate structured answer"],
                    confidence_tier=ConfidenceTier.NONE,
                    confidence_factors={},
                    validation_passed=False,
                    validation_errors=["JSON parsing failed"],
                ),
                usage,
            )

        # Validate
        validated = self._validate_answer(parsed, sources)
        return validated, usage

    def _parse_answer_json(self, response: str) -> dict[str, Any] | None:
        """Parse JSON from LLM response."""
        # Try direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from response
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _validate_answer(
        self,
        parsed: dict[str, Any],
        sources: list[RetrievedSource],
    ) -> ValidatedAnswer:
        """Validate the parsed answer."""
        errors = []
        valid_source_ids = {s.index for s in sources}

        sections = []
        for i, section_data in enumerate(parsed.get("sections", [])):
            text = section_data.get("text", "")
            source_ids = section_data.get("source_ids", [])

            if not text:
                errors.append(f"Section {i} has no text")
                continue

            if not source_ids:
                errors.append(f"Section {i} has no source_ids")
                continue

            # Validate source_ids exist
            invalid_ids = [sid for sid in source_ids if sid not in valid_source_ids]
            if invalid_ids:
                errors.append(f"Section {i} references invalid source_ids: {invalid_ids}")
                # Remove invalid IDs but keep valid ones
                source_ids = [sid for sid in source_ids if sid in valid_source_ids]

            if source_ids:  # Only add if we have valid sources
                sections.append(AnswerSection(text=text, source_ids=source_ids))

        unknowns = parsed.get("unknowns", [])

        # Calculate confidence
        confidence_tier, confidence_factors = self._calculate_confidence(sections, sources)

        return ValidatedAnswer(
            sections=sections,
            unknowns=unknowns,
            confidence_tier=confidence_tier,
            confidence_factors=confidence_factors,
            validation_passed=len(errors) == 0,
            validation_errors=errors,
        )

    def _calculate_confidence(
        self,
        sections: list[AnswerSection],
        sources: list[RetrievedSource],
    ) -> tuple[ConfidenceTier, dict[str, Any]]:
        """Calculate confidence tier based on evidence coverage."""
        if not sections:
            return ConfidenceTier.NONE, {"reason": "no_sections"}

        # Collect all cited source IDs
        cited_ids = set()
        for section in sections:
            cited_ids.update(section.source_ids)

        # Get cited sources
        cited_sources = [s for s in sources if s.index in cited_ids]

        # Count unique files
        unique_files = len(set(s.file_path for s in cited_sources))

        # Check for entrypoints (routes, controllers for Laravel)
        has_entrypoints = any(
            "controller" in s.file_path.lower() or "route" in s.file_path.lower()
            for s in cited_sources
        )

        factors = {
            "citation_count": len(cited_ids),
            "unique_files": unique_files,
            "has_entrypoints": has_entrypoints,
            "section_count": len(sections),
        }

        # Determine tier
        if len(cited_ids) >= 3 and unique_files >= 2:
            return ConfidenceTier.HIGH, factors
        elif len(cited_ids) >= 2:
            return ConfidenceTier.MEDIUM, factors
        elif len(cited_ids) >= 1:
            return ConfidenceTier.LOW, factors
        else:
            return ConfidenceTier.NONE, factors

    def _format_answer_text(self, validated: ValidatedAnswer) -> str:
        """Format validated answer as readable text."""
        parts = []

        for section in validated.sections:
            # Add source references
            refs = ", ".join(f"[{sid}]" for sid in section.source_ids)
            parts.append(f"{section.text} {refs}")

        if validated.unknowns:
            parts.append("\n**Could not determine:**")
            for unknown in validated.unknowns:
                parts.append(f"- {unknown}")

        return "\n\n".join(parts)

    def _build_citations(
        self,
        sources: list[RetrievedSource],
        validated: ValidatedAnswer,
        repo: Repository,
    ) -> list[dict[str, Any]]:
        """Build citation objects for response."""
        # Get all cited source IDs
        cited_ids = set()
        for section in validated.sections:
            cited_ids.update(section.source_ids)

        citations = []
        for source in sources:
            if source.index in cited_ids:
                github_url = (
                    f"https://github.com/{repo.full_name}/blob/"
                    f"{repo.last_indexed_commit}/{source.file_path}"
                    f"#L{source.start_line}-L{source.end_line}"
                )

                citations.append(
                    {
                        "source_index": source.index,
                        "file_path": source.file_path,
                        "start_line": source.start_line,
                        "end_line": source.end_line,
                        "snippet": source.content,
                        "symbol_name": source.symbol_name,
                        "github_url": github_url,
                    }
                )

        return citations

    def _no_evidence_result(self, question: str) -> QAResult:
        """Return result when no evidence found."""
        return QAResult(
            answer_text=(
                f'I could not find enough evidence in the codebase to answer: "{question}"\n\n'
                "Try asking about specific class or function names."
            ),
            citations=[],
            confidence_tier=ConfidenceTier.NONE,
            unknowns=[question],
            has_sufficient_evidence=False,
        )

    async def _get_repo(self, repo_id: str) -> Repository:
        """Get repository record."""
        result = await self.db.execute(select(Repository).where(Repository.id == repo_id))
        return result.scalar_one()

    async def _get_cached_snippet(
        self,
        repo_id: str,
        commit_sha: str,
        file_path: str,
        start_line: int,
        end_line: int,
    ) -> str | None:
        """Get cached snippet if available."""
        result = await self.db.execute(
            select(SnippetCache).where(
                SnippetCache.repo_id == repo_id,
                SnippetCache.commit_sha == commit_sha,
                SnippetCache.file_path == file_path,
                SnippetCache.start_line == start_line,
                SnippetCache.end_line == end_line,
                SnippetCache.expires_at > text("NOW()"),
            )
        )
        cache = result.scalar_one_or_none()
        return cache.content if cache else None

    async def _cache_snippet(
        self,
        repo_id: str,
        commit_sha: str,
        file_path: str,
        start_line: int,
        end_line: int,
        content: str,
    ) -> None:
        """Cache snippet for later use."""
        from datetime import datetime, timedelta

        cache = SnippetCache(
            repo_id=repo_id,
            commit_sha=commit_sha,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content=content,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        self.db.add(cache)
        await self.db.commit()

    async def _store_answer(
        self,
        repo_id: str,
        user_id: str,
        question: str,
        validated: ValidatedAnswer,
        citations: list[dict[str, Any]],
        usage: dict[str, int],
    ) -> None:
        """Store answer in database."""
        answer = Answer(
            repo_id=repo_id,
            user_id=user_id,
            question=question,
            answer_text=self._format_answer_text(validated),
            answer_sections=[
                {"text": s.text, "source_ids": s.source_ids} for s in validated.sections
            ],
            unknowns=validated.unknowns,
            confidence_tier=validated.confidence_tier.value,
            confidence_factors=validated.confidence_factors,
            validation_passed=validated.validation_passed,
            validation_errors=validated.validation_errors,
            llm_model=self.llm_service.model,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
        self.db.add(answer)
        await self.db.flush()

        for cite in citations:
            citation = Citation(
                answer_id=answer.id,
                source_index=cite["source_index"],
                file_path=cite["file_path"],
                start_line=cite["start_line"],
                end_line=cite["end_line"],
                snippet=cite["snippet"][:500],
                symbol_name=cite.get("symbol_name"),
            )
            self.db.add(citation)

        await self.db.commit()

