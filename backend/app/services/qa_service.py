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
class QuotedSpan:
    """A quoted span from source code that supports a claim."""

    source_id: int
    quoted_text: str  # Exact text from source
    verified: bool = False  # True if quote was found in source


@dataclass
class AnswerSection:
    """A section of the answer with its sources and evidence."""

    text: str
    source_ids: list[int]
    quoted_spans: list[QuotedSpan] = field(default_factory=list)


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
2. Every claim MUST reference at least one source_id AND include a quoted_span
3. The quoted_span MUST be an EXACT substring from the source code (copy-paste, no modifications)
4. If you cannot find exact evidence, put the question in "unknowns"
5. Do NOT invent file paths, line numbers, or quotes
6. Do NOT paraphrase code - quote it exactly

OUTPUT SCHEMA:
{{
    "sections": [
        {{
            "text": "The UserController handles user authentication by calling the AuthService.",
            "source_ids": [1, 3],
            "quoted_spans": [
                {{"source_id": 1, "quote": "class UserController"}},
                {{"source_id": 3, "quote": "$this->authService->authenticate($credentials)"}}
            ]
        }}
    ],
    "unknowns": [
        "I could not find where password reset emails are sent"
    ]
}}

IMPORTANT: Each quoted_span.quote must be a verbatim substring that appears in the corresponding source. I will verify these quotes exist.

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
        from app.services.claim_validator import ClaimValidator
        self.claim_validator = ClaimValidator()

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

            vector_results = await self.embedding_service.search_repo(
                repo_id,
                question,
                limit=15,
            )
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
        """Extract meaningful keywords from query with code-aware tokenization.

        Preserves:
        - camelCase tokens (split into parts but keep original)
        - snake_case tokens (split into parts but keep original)
        - ALLCAPS tokens (API, JWT, etc.)
        - Digits in tokens (OAuth2, v2, S3)
        - Special symbols (__init__, ::, /)
        - File paths (app/Http/Controllers)
        """
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "how", "what", "where", "when", "why", "which", "who",
            "does", "do", "did", "has", "have", "had",
            "in", "on", "at", "to", "for", "of", "with", "by",
            "can", "could", "would", "should", "will",
            "this", "that", "these", "those", "it", "its",
            "and", "or", "but", "if", "then", "else",
            "my", "your", "our", "their", "i", "you", "we", "they",
        }

        keywords = []
        seen = set()

        def add_keyword(kw: str) -> None:
            """Add keyword if valid and not seen."""
            if kw and kw.lower() not in stopwords and kw not in seen:
                # Keep ALLCAPS as-is, otherwise lowercase for matching
                seen.add(kw)
                keywords.append(kw)

        # Extract file paths (e.g., app/Http/Controllers/UserController.php)
        file_paths = re.findall(r'[\w./\\-]+\.(?:php|py|js|ts|tsx|jsx|java|go|rs|rb)', query)
        for path in file_paths:
            add_keyword(path)
            # Also extract the filename without extension
            filename = path.split('/')[-1].split('\\')[-1].rsplit('.', 1)[0]
            add_keyword(filename)

        # Extract qualified names (e.g., AuthService::login, App\Models\User)
        qualified = re.findall(r'\b[\w]+(?:(?:::|\.|\\)[\w]+)+\b', query)
        for q in qualified:
            add_keyword(q)
            # Also extract individual parts
            parts = re.split(r'::|\\|\.', q)
            for part in parts:
                if len(part) > 1:
                    add_keyword(part)

        # Extract special Python/Ruby dunders (__init__, __call__, etc.)
        dunders = re.findall(r'__\w+__', query)
        for d in dunders:
            add_keyword(d)

        # Extract tokens with digits (OAuth2, S3, v2, etc.) - preserve as-is
        alphanumeric = re.findall(r'\b[A-Za-z]+\d+\w*\b|\b\d+[A-Za-z]+\w*\b', query)
        for an in alphanumeric:
            add_keyword(an)

        # Extract ALLCAPS tokens (API, JWT, HTTP, etc.)
        allcaps = re.findall(r'\b[A-Z]{2,}\b', query)
        for ac in allcaps:
            add_keyword(ac)

        # Extract camelCase and PascalCase - keep original AND split parts
        camel_pattern = re.findall(r'\b[a-z]+(?:[A-Z][a-z]+)+\b|\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', query)
        for camel in camel_pattern:
            add_keyword(camel)
            # Split camelCase into parts
            parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)', camel)
            for part in parts:
                if len(part) > 2:
                    add_keyword(part)

        # Extract snake_case - keep original AND split parts
        snake_pattern = re.findall(r'\b\w+(?:_\w+)+\b', query)
        for snake in snake_pattern:
            add_keyword(snake)
            parts = snake.split('_')
            for part in parts:
                if len(part) > 2:
                    add_keyword(part)

        # Extract remaining meaningful words (not already captured)
        remaining = re.findall(r'\b[A-Za-z][A-Za-z0-9]*\b', query)
        for word in remaining:
            if len(word) > 2:
                add_keyword(word)

        # Prioritize: keep all keywords but limit total for query efficiency
        # Sort by length (longer = more specific) then alphabetically
        keywords.sort(key=lambda k: (-len(k), k.lower()))

        return keywords[:10]  # Allow more keywords for better recall

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
            # Return degraded evidence-only response instead of "nothing"
            # This allows users to still see retrieved sources
            logger.warning("JSON parsing failed, returning evidence-only response")
            return (
                ValidatedAnswer(
                    sections=[
                        AnswerSection(
                            text=(
                                "I found relevant code but couldn't structure a complete answer. "
                                "Please review the cited sources directly."
                            ),
                            source_ids=[s.index for s in sources[:3]],  # Top 3 sources
                            quoted_spans=[],  # No verified quotes
                        )
                    ],
                    unknowns=[
                        "Answer generation failed - showing raw sources",
                        "Please review the citations manually",
                    ],
                    confidence_tier=ConfidenceTier.NONE,
                    confidence_factors={"degraded_mode": True, "parse_failed": True},
                    validation_passed=False,
                    validation_errors=["JSON parsing failed - evidence-only mode"],
                ),
                usage,
            )

        # Validate
        validated = self._validate_answer(parsed, sources)
        return validated, usage

    def _parse_answer_json(self, response: str) -> dict[str, Any] | None:
        """Parse JSON from LLM response with multiple repair strategies.

        Handles:
        - Direct JSON
        - JSON in markdown code blocks
        - JSON with trailing commas
        - JSON with explanation text before/after
        - Truncated JSON (attempts repair)
        """
        # Strategy 1: Direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code block
        code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find JSON object in response (greedy)
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            json_str = json_match.group()

            # Try direct parse
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            # Strategy 4: Repair common issues
            repaired = self._repair_json(json_str)
            if repaired:
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    pass

        # Strategy 5: Try to find last complete JSON object (for truncated responses)
        # Look for balanced braces
        brace_count = 0
        last_complete_end = -1
        start_idx = response.find('{')

        if start_idx >= 0:
            for i, char in enumerate(response[start_idx:], start_idx):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_complete_end = i + 1
                        break

            if last_complete_end > start_idx:
                try:
                    return json.loads(response[start_idx:last_complete_end])
                except json.JSONDecodeError:
                    repaired = self._repair_json(response[start_idx:last_complete_end])
                    if repaired:
                        try:
                            return json.loads(repaired)
                        except json.JSONDecodeError:
                            pass

        logger.warning("All JSON parsing strategies failed")
        return None

    def _repair_json(self, json_str: str) -> str | None:
        """Attempt to repair common JSON issues."""
        try:
            repaired = json_str

            # Remove trailing commas before ] or }
            repaired = re.sub(r',\s*([\]}])', r'\1', repaired)

            # Fix unquoted keys (simple cases)
            repaired = re.sub(r'(\{|,)\s*(\w+)\s*:', r'\1"\2":', repaired)

            # Remove control characters
            repaired = re.sub(r'[\x00-\x1f]', '', repaired)

            # Fix single quotes to double quotes (risky but sometimes needed)
            # Only if no double quotes present in values
            if "'" in repaired and '"' not in repaired:
                repaired = repaired.replace("'", '"')

            return repaired
        except Exception:
            return None

    def _validate_answer(
        self,
        parsed: dict[str, Any],
        sources: list[RetrievedSource],
    ) -> ValidatedAnswer:
        """Validate the parsed answer with claim-to-evidence verification."""
        errors = []
        valid_source_ids = {s.index for s in sources}
        source_by_id = {s.index: s for s in sources}

        sections = []
        total_quotes = 0
        verified_quotes = 0

        for i, section_data in enumerate(parsed.get("sections", [])):
            text = section_data.get("text", "")
            source_ids = section_data.get("source_ids", [])
            raw_quotes = section_data.get("quoted_spans", [])

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
                source_ids = [sid for sid in source_ids if sid in valid_source_ids]

            if not source_ids:
                continue

            # Validate quoted spans - THIS IS THE CRITICAL VERIFICATION
            verified_spans = []
            for quote_data in raw_quotes:
                quote_source_id = quote_data.get("source_id")
                quote_text = quote_data.get("quote", "")

                if not quote_text or not quote_source_id:
                    continue

                total_quotes += 1

                if quote_source_id not in source_by_id:
                    errors.append(f"Section {i}: quote references invalid source {quote_source_id}")
                    continue

                # CRITICAL: Verify the quote actually exists in the source using ClaimValidator
                source = source_by_id[quote_source_id]
                # Use ClaimValidator for verification
                quote_verified = self.claim_validator.verify_quote_in_source(quote_text, source.content)

                verified_spans.append(
                    QuotedSpan(
                        source_id=quote_source_id,
                        quoted_text=quote_text,
                        verified=quote_verified,
                    )
                )

                if quote_verified:
                    verified_quotes += 1
                else:
                    errors.append(
                        f"Section {i}: quote '{quote_text[:50]}...' not found in source {quote_source_id}"
                    )

            # Section is only valid if it has at least one verified quote
            has_verified_evidence = any(span.verified for span in verified_spans)

            if not raw_quotes:
                # No quotes provided - section lacks evidence
                errors.append(f"Section {i} has no quoted_spans - claims not verifiable")
                # Still include but mark as unverified
                sections.append(
                    AnswerSection(
                        text=text,
                        source_ids=source_ids,
                        quoted_spans=[],
                    )
                )
            elif has_verified_evidence:
                sections.append(
                    AnswerSection(
                        text=text,
                        source_ids=source_ids,
                        quoted_spans=verified_spans,
                    )
                )
            else:
                # Has quotes but none verified - reject section
                errors.append(f"Section {i}: no quotes could be verified - rejecting section")

        unknowns = parsed.get("unknowns", [])

        # Calculate confidence with quote verification stats
        confidence_tier, confidence_factors = self._calculate_confidence(
            sections, sources, total_quotes, verified_quotes
        )

        return ValidatedAnswer(
            sections=sections,
            unknowns=unknowns,
            confidence_tier=confidence_tier,
            confidence_factors=confidence_factors,
            validation_passed=len(errors) == 0 and verified_quotes > 0,
            validation_errors=errors,
        )

    def _verify_quote_in_source(self, quote: str, source_content: str) -> bool:
        """Verify that a quote exists in the source content.

        Uses fuzzy matching to handle minor whitespace differences.
        """
        if not quote or not source_content:
            return False

        # Normalize whitespace for comparison
        def normalize(s: str) -> str:
            return " ".join(s.split())

        normalized_quote = normalize(quote)
        normalized_source = normalize(source_content)

        # Exact match (normalized)
        if normalized_quote in normalized_source:
            return True

        # Try case-insensitive match
        if normalized_quote.lower() in normalized_source.lower():
            return True

        # Try without leading/trailing quotes
        stripped_quote = quote.strip("'\"` ")
        if stripped_quote and stripped_quote in source_content:
            return True

        return False

    def _calculate_confidence(
        self,
        sections: list[AnswerSection],
        sources: list[RetrievedSource],
        total_quotes: int = 0,
        verified_quotes: int = 0,
    ) -> tuple[ConfidenceTier, dict[str, Any]]:
        """Calculate confidence tier based on evidence quality, not just count.

        Scoring factors:
        - Quote verification rate (critical)
        - Retrieval score distribution (higher scores = more relevant)
        - Source diversity (multiple files)
        - Sections with verified evidence
        """
        if not sections:
            return ConfidenceTier.NONE, {"reason": "no_sections"}

        # Collect all cited source IDs
        cited_ids = set()
        verified_section_count = 0

        for section in sections:
            cited_ids.update(section.source_ids)
            # Count sections with at least one verified quote
            if any(span.verified for span in section.quoted_spans):
                verified_section_count += 1

        # Get cited sources
        cited_sources = [s for s in sources if s.index in cited_ids]
        if not cited_sources:
            return ConfidenceTier.NONE, {"reason": "no_cited_sources"}

        # Calculate metrics
        unique_files = len(set(s.file_path for s in cited_sources))
        avg_score = sum(s.score for s in cited_sources) / len(cited_sources)
        max_score = max(s.score for s in cited_sources)
        min_score = min(s.score for s in cited_sources)

        # Quote verification rate (0.0 to 1.0)
        verification_rate = verified_quotes / total_quotes if total_quotes > 0 else 0.0

        # Check for entrypoints (routes, controllers)
        has_entrypoints = any(
            "controller" in s.file_path.lower() or "route" in s.file_path.lower()
            for s in cited_sources
        )

        factors = {
            "citation_count": len(cited_ids),
            "unique_files": unique_files,
            "has_entrypoints": has_entrypoints,
            "section_count": len(sections),
            "verified_section_count": verified_section_count,
            "total_quotes": total_quotes,
            "verified_quotes": verified_quotes,
            "verification_rate": round(verification_rate, 2),
            "avg_retrieval_score": round(avg_score, 3),
            "max_retrieval_score": round(max_score, 3),
            "min_retrieval_score": round(min_score, 3),
        }

        # CONFIDENCE SCORING RULES:
        #
        # NONE: No verified evidence
        # LOW:  Some evidence but weak verification or low retrieval scores
        # MEDIUM: Good verification rate with decent retrieval quality
        # HIGH: Strong verification + multiple verified sources from multiple files

        # Rule 1: Must have at least one verified quote for any confidence
        if verified_quotes == 0:
            factors["reason"] = "no_verified_quotes"
            return ConfidenceTier.NONE, factors

        # Rule 2: Verification rate must be >= 50% for MEDIUM, >= 75% for HIGH
        if verification_rate < 0.5:
            factors["reason"] = "low_verification_rate"
            return ConfidenceTier.LOW, factors

        # Rule 3: Need multiple verified sections from multiple files for HIGH
        if (
            verified_section_count >= 2
            and unique_files >= 2
            and verification_rate >= 0.75
            and avg_score >= 0.5
        ):
            factors["reason"] = "strong_multi_source_evidence"
            return ConfidenceTier.HIGH, factors

        # Rule 4: Good verification with decent retrieval for MEDIUM
        if verification_rate >= 0.5 and verified_section_count >= 1:
            # Penalize if retrieval scores are weak
            if avg_score < 0.3:
                factors["reason"] = "weak_retrieval_scores"
                return ConfidenceTier.LOW, factors
            factors["reason"] = "good_verification_moderate_coverage"
            return ConfidenceTier.MEDIUM, factors

        # Default to LOW
        factors["reason"] = "default_low_confidence"
        return ConfidenceTier.LOW, factors

    def _format_answer_text(self, validated: ValidatedAnswer) -> str:
        """Format validated answer as readable text with evidence quality indicators."""
        parts = []

        for section in validated.sections:
            # Add source references
            refs = ", ".join(f"[{sid}]" for sid in section.source_ids)

            # Add verification status
            verified_count = sum(1 for span in section.quoted_spans if span.verified)
            total_spans = len(section.quoted_spans)

            if total_spans > 0:
                verification_indicator = f" ✓{verified_count}/{total_spans}"
            else:
                verification_indicator = " ⚠️unverified"

            parts.append(f"{section.text} {refs}{verification_indicator}")

        if validated.unknowns:
            parts.append("\n**Could not determine:**")
            for unknown in validated.unknowns:
                parts.append(f"- {unknown}")

        # Add confidence explanation
        if validated.confidence_factors.get("reason"):
            parts.append(f"\n_Confidence: {validated.confidence_tier.value} ({validated.confidence_factors['reason']})_")

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
        """Store answer in database with full evidence chain."""
        # Serialize sections with quoted spans
        serialized_sections = []
        for s in validated.sections:
            section_data = {
                "text": s.text,
                "source_ids": s.source_ids,
                "quoted_spans": [
                    {
                        "source_id": span.source_id,
                        "quoted_text": span.quoted_text,
                        "verified": span.verified,
                    }
                    for span in s.quoted_spans
                ],
            }
            serialized_sections.append(section_data)

        answer = Answer(
            repo_id=repo_id,
            user_id=user_id,
            question=question,
            answer_text=self._format_answer_text(validated),
            answer_sections=serialized_sections,
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
