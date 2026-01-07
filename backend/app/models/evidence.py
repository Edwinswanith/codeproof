"""Evidence models for findings.

All findings must have hard evidence: file path, line numbers, code snippet,
and clear explanation of why the rule triggered.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ConfidenceLevel(str, Enum):
    """Confidence levels for findings."""

    HIGH = "high"  # Exact pattern match, clear evidence
    MEDIUM = "medium"  # Structural match, good evidence
    LOW = "low"  # Heuristic match, weak evidence
    SPECULATIVE = "speculative"  # No hard evidence, downgrade severity


@dataclass
class Evidence:
    """Structured evidence for a finding.

    Every finding must have complete evidence: file location, code snippet,
    and clear explanation of why the rule triggered.
    """

    file_path: str
    start_line: int
    end_line: int
    code_snippet: str  # Exact quoted code (3-5 lines with match highlighted)
    rule_name: str  # Name of the rule/pattern that triggered
    rule_trigger_reason: str  # Why this rule matched (specific explanation)
    pattern_matched: Optional[str] = None  # The actual matched pattern/text
    context_lines: str = ""  # Surrounding code for context (optional)
    source: Optional[str] = None  # Source location (for dataflow analysis)
    sink: Optional[str] = None  # Sink location (for dataflow analysis)


@dataclass
class FindingMetadata:
    """Additional metadata for findings."""

    rule_id: str  # Unique identifier for the rule that triggered
    data_types: list[str]  # Data types involved (email, phone, PII, credentials, etc.)
    confidence: ConfidenceLevel
    confidence_reason: str  # Explanation of confidence level


@dataclass
class SpeculativeFinding:
    """Finding without hard evidence - automatically downgraded severity.
    
    Used when a finding is detected but cannot be verified with complete
    evidence (file, line, snippet, reason). Severity is automatically
    downgraded to INFO to prevent false positives.
    """
    
    severity: str  # Always INFO for speculative findings
    category: str
    file_path: str
    start_line: int
    end_line: int
    evidence: Evidence  # May have incomplete evidence
    rule_id: str
    data_types: list[str]
    reason_for_speculation: str  # Why this is speculative (missing evidence)
    original_severity: str  # What severity would be with full evidence

