"""Pattern-based analyzer helpers."""

from dataclasses import dataclass, field
import re
from typing import Any, Iterable, Optional

from app.analyzers.base import FindingMatch


@dataclass
class PatternRule:
    rule_id: str
    category: str
    title: str
    description: str
    severity: str
    confidence: str
    remediation: str
    pattern: str
    flags: int = re.IGNORECASE
    tags: list[str] = field(default_factory=list)
    impact: dict[str, Any] = field(default_factory=dict)
    likelihood: dict[str, Any] = field(default_factory=dict)
    normalized_source: Optional[str] = None
    normalized_sink: Optional[str] = None


def _line_for_offset(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def _snippet_for_match(content: str, start_line: int, end_line: int, max_lines: int = 6) -> str:
    lines = content.splitlines()
    start_idx = max(0, start_line - 1)
    end_idx = min(len(lines), end_line)
    snippet_lines = lines[start_idx:end_idx]
    if len(snippet_lines) > max_lines:
        snippet_lines = snippet_lines[:max_lines]
    return "\n".join(snippet_lines)


def match_patterns(
    file_path: str,
    content: str,
    rules: Iterable[PatternRule],
) -> list[FindingMatch]:
    matches: list[FindingMatch] = []
    for rule in rules:
        for match in re.finditer(rule.pattern, content, rule.flags):
            start_line = _line_for_offset(content, match.start())
            end_line = _line_for_offset(content, match.end())
            snippet = _snippet_for_match(content, start_line, end_line)
            matches.append(
                FindingMatch(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    title=rule.title,
                    description=rule.description,
                    severity=rule.severity,
                    confidence=rule.confidence,
                    remediation=rule.remediation,
                    tags=rule.tags,
                    impact=rule.impact,
                    likelihood=rule.likelihood,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    snippet=snippet,
                    normalized_source=rule.normalized_source,
                    normalized_sink=rule.normalized_sink,
                )
            )
    return matches
