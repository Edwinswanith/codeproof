"""Claim validation service for Q&A answers.

Validates that quoted code spans in citations actually exist in the cited files,
ensuring all claims are backed by hard evidence.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Claim:
    """A claim extracted from an answer."""

    text: str
    source_id: int
    quoted_span: str  # The quoted code that should support this claim
    file_path: str
    line_start: int
    line_end: int


@dataclass
class Citation:
    """Citation information for validation."""

    source_id: int
    file_path: str
    start_line: int
    end_line: int
    code_snippet: str  # The actual code from the file
    symbol_name: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of claim validation."""

    verified: bool  # True if all claims are verified
    claims_verified: int
    claims_failed: int
    failed_claims: list[Claim]  # Claims that couldn't be verified
    validation_errors: list[str]


class ClaimValidator:
    """Service for validating claims in Q&A answers."""

    def validate_claims(
        self, answer_text: str, citations: list[Citation]
    ) -> ValidationResult:
        """Validate all claims in an answer against citations.

        Args:
            answer_text: The answer text (may contain JSON structure)
            citations: List of citations with code snippets

        Returns:
            ValidationResult with verification status
        """
        # Extract claims from answer (could be JSON structured or plain text)
        claims = self.extract_claims(answer_text, citations)

        verified_count = 0
        failed_count = 0
        failed_claims = []
        errors = []

        # Build citation lookup
        citation_map = {cite.source_id: cite for cite in citations}

        for claim in claims:
            citation = citation_map.get(claim.source_id)
            if not citation:
                failed_count += 1
                failed_claims.append(claim)
                errors.append(f"Citation {claim.source_id} not found")
                continue

            is_verified = self.verify_claim_in_code(claim, citation)
            if is_verified:
                verified_count += 1
            else:
                failed_count += 1
                failed_claims.append(claim)
                errors.append(
                    f"Quoted span not found in {citation.file_path}:{citation.start_line}-{citation.end_line}"
                )

        all_verified = failed_count == 0

        return ValidationResult(
            verified=all_verified,
            claims_verified=verified_count,
            claims_failed=failed_count,
            failed_claims=failed_claims,
            validation_errors=errors,
        )

    def extract_claims(self, answer_text: str, citations: list[Citation]) -> list[Claim]:
        """Extract claims from answer text.

        The answer may be JSON structured with quoted_spans, or plain text.
        This tries to extract claims from both formats.
        """
        claims = []

        # Try to parse as JSON first (structured format)
        try:
            import json

            # Try to extract JSON from answer (may have prefix text)
            json_match = re.search(r"\{.*\}", answer_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                sections = data.get("sections", [])

                citation_map = {cite.source_id: cite for cite in citations}

                for section in sections:
                    text = section.get("text", "")
                    quoted_spans = section.get("quoted_spans", [])
                    source_ids = section.get("source_ids", [])

                    for span_data in quoted_spans:
                        source_id = span_data.get("source_id")
                        quote = span_data.get("quote", "")

                        if source_id and quote:
                            citation = citation_map.get(source_id)
                            if citation:
                                claims.append(
                                    Claim(
                                        text=text,
                                        source_id=source_id,
                                        quoted_span=quote,
                                        file_path=citation.file_path,
                                        line_start=citation.start_line,
                                        line_end=citation.end_line,
                                    )
                                )
        except (json.JSONDecodeError, KeyError, AttributeError):
            # Not JSON format, try to extract from plain text
            # Look for code blocks or quoted strings
            pass

        return claims

    def verify_quote_in_source(self, quote_text: str, source_content: str) -> bool:
        """Verify that a quote exists in source content.
        
        Simplified method for direct quote verification.
        
        Args:
            quote_text: The quoted text to verify
            source_content: The source code content
            
        Returns:
            True if quote is found in source
        """
        if not quote_text or not source_content:
            return False

        quoted_span = quote_text.strip()
        code_snippet = source_content

        # Normalize whitespace for comparison
        normalized_quote = re.sub(r"\s+", " ", quoted_span.strip())
        normalized_code = re.sub(r"\s+", " ", code_snippet.strip())

        # Try exact match first (case-sensitive)
        if quoted_span in code_snippet:
            return True

        # Try normalized match
        if normalized_quote in normalized_code:
            return True

        # Try case-insensitive match
        if quoted_span.lower() in code_snippet.lower():
            return True

        # Try to find partial matches (for multi-line quotes)
        quote_lines = [line.strip() for line in quoted_span.split("\n") if line.strip()]
        code_lines = [line.strip() for line in code_snippet.split("\n") if line.strip()]

        if len(quote_lines) > 1:
            # Multi-line quote: check if all lines appear in order
            code_text = "\n".join(code_lines)
            quote_text_combined = "\n".join(quote_lines)

            if quote_text_combined in code_text:
                return True

            # Try with normalized whitespace
            normalized_quote_text = re.sub(r"\s+", " ", quote_text_combined)
            normalized_code_text = re.sub(r"\s+", " ", code_text)
            if normalized_quote_text in normalized_code_text:
                return True

        return False

    def verify_claim_in_code(self, claim: Claim, citation: Citation) -> bool:
        """Verify that a quoted span exists in the cited code.

        Args:
            claim: The claim with quoted span
            citation: The citation with code snippet

        Returns:
            True if quoted span is found in citation code
        """
        quoted_span = claim.quoted_span.strip()
        code_snippet = citation.code_snippet

        if not quoted_span:
            return False

        # Normalize whitespace for comparison
        # Replace multiple whitespace with single space
        normalized_quote = re.sub(r"\s+", " ", quoted_span.strip())
        normalized_code = re.sub(r"\s+", " ", code_snippet.strip())

        # Try exact match first (case-sensitive)
        if quoted_span in code_snippet:
            return True

        # Try normalized match
        if normalized_quote in normalized_code:
            return True

        # Try case-insensitive match
        if quoted_span.lower() in code_snippet.lower():
            return True

        # Try to find partial matches (for multi-line quotes)
        # Split quote into lines and check if all lines exist
        quote_lines = [line.strip() for line in quoted_span.split("\n") if line.strip()]
        code_lines = [line.strip() for line in code_snippet.split("\n") if line.strip()]

        if len(quote_lines) > 1:
            # Multi-line quote: check if all lines appear in order
            code_text = "\n".join(code_lines)
            quote_text = "\n".join(quote_lines)

            if quote_text in code_text:
                return True

            # Try with normalized whitespace
            normalized_quote_text = re.sub(r"\s+", " ", quote_text)
            normalized_code_text = re.sub(r"\s+", " ", code_text)
            if normalized_quote_text in normalized_code_text:
                return True

        # If quote is very short (single word/token), check if it appears
        # This is less reliable but better than nothing
        if len(quote_lines) == 1 and len(quoted_span.split()) <= 3:
            words = quoted_span.split()
            code_words = set(code_snippet.split())
            if all(word in code_words for word in words):
                return True

        return False

    def validate_citation_spans(
        self, citations: list[Citation], file_contents: dict[str, str]
    ) -> dict[int, bool]:
        """Validate that citation code snippets exist in actual files.

        Args:
            citations: List of citations to validate
            file_contents: Dict mapping file_path -> file content

        Returns:
            Dict mapping source_id -> verification status
        """
        validation_status = {}

        for citation in citations:
            file_content = file_contents.get(citation.file_path)
            if not file_content:
                validation_status[citation.source_id] = False
                continue

            # Extract lines from file
            lines = file_content.split("\n")
            if citation.start_line < 1 or citation.end_line > len(lines):
                validation_status[citation.source_id] = False
                continue

            # Get actual code from file
            file_snippet = "\n".join(
                lines[citation.start_line - 1 : citation.end_line]
            )

            # Check if citation snippet matches file content
            # Normalize for comparison
            normalized_citation = re.sub(r"\s+", " ", citation.code_snippet.strip())
            normalized_file = re.sub(r"\s+", " ", file_snippet.strip())

            validation_status[citation.source_id] = (
                normalized_citation in normalized_file
                or citation.code_snippet in file_snippet
            )

        return validation_status

