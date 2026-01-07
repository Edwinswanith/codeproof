"""Base analyzer interfaces for repo intelligence scans."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AnalyzerContext:
    """Shared context for analyzers."""

    repo_path: str
    file_contents: dict[str, str]
    parse_result: Any
    coverage_report: Any


@dataclass
class FindingMatch:
    """Finding match emitted by analyzers."""

    rule_id: str
    category: str
    title: str
    description: str
    severity: str
    confidence: str
    remediation: str
    tags: list[str] = field(default_factory=list)
    impact: dict[str, Any] = field(default_factory=dict)
    likelihood: dict[str, Any] = field(default_factory=dict)
    file_path: str = ""
    start_line: int = 1
    end_line: int = 1
    snippet: str = ""
    normalized_source: Optional[str] = None
    normalized_sink: Optional[str] = None
    symbol: Optional[str] = None


class Analyzer:
    """Base class for analyzers."""

    name: str = "base"

    def analyze(self, context: AnalyzerContext) -> list[FindingMatch]:
        raise NotImplementedError
