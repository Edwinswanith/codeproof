"""Evidence snippet extraction and redaction."""

import hashlib
import re


class EvidenceService:
    """Service for extracting and redacting evidence snippets."""

    REDACTION_PATTERNS = [
        r"ghp_[a-zA-Z0-9]{36,}",
        r"github_pat_[a-zA-Z0-9_]{22,}",
        r"ghu_[a-zA-Z0-9]{36,}",
        r"ghs_[a-zA-Z0-9]{36,}",
        r"gho_[a-zA-Z0-9]{36,}",
        r"xoxb-[a-zA-Z0-9-]+",
        r"xoxp-[a-zA-Z0-9-]+",
        r"AKIA[0-9A-Z]{16}",
        r"sk-[a-zA-Z0-9]{48,}",
        r"glpat-[a-zA-Z0-9_-]{20,}",
        r"(?i)(api_key|secret|token|password)\\s*=\\s*[\"'][^\"']+[\"']",
    ]

    MAX_SNIPPET_LINES = 12
    CONTEXT_LINES = 2
    MAX_SNIPPET_CHARS = 800

    def redact(self, text: str) -> str:
        redacted = text
        for pattern in self.REDACTION_PATTERNS:
            redacted = re.sub(pattern, "[REDACTED]", redacted)
        return redacted

    def extract_snippet(
        self,
        content: str,
        start_line: int,
        end_line: int,
    ) -> tuple[str, str | None, str | None]:
        lines = content.splitlines()
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)

        context_start = max(0, start_idx - self.CONTEXT_LINES)
        context_end = min(len(lines), end_idx + self.CONTEXT_LINES)

        snippet_lines = lines[start_idx:end_idx]
        if len(snippet_lines) > self.MAX_SNIPPET_LINES:
            snippet_lines = snippet_lines[: self.MAX_SNIPPET_LINES]

        snippet_text = "\n".join(snippet_lines)
        context_before = "\n".join(lines[context_start:start_idx]) if context_start < start_idx else None
        context_after = "\n".join(lines[end_idx:context_end]) if end_idx < context_end else None

        snippet_text = self.redact(snippet_text)
        if context_before:
            context_before = self.redact(context_before)
        if context_after:
            context_after = self.redact(context_after)

        if len(snippet_text) > self.MAX_SNIPPET_CHARS:
            snippet_text = snippet_text[: self.MAX_SNIPPET_CHARS] + "..."

        return snippet_text, context_before, context_after

    def hash_snippet(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
