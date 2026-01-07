"""Privacy analyzer for data inventory and logging signals."""

from app.analyzers.base import Analyzer, AnalyzerContext, FindingMatch
from app.analyzers.patterns import PatternRule, match_patterns


class PrivacyAnalyzer(Analyzer):
    name = "privacy"

    def analyze(self, context: AnalyzerContext) -> list[FindingMatch]:
        rules = [
            PatternRule(
                rule_id="PRIV-001",
                category="privacy",
                title="Personal data field detected",
                description="Detected likely personal data fields (email, phone, address).",
                severity="medium",
                confidence="low",
                remediation="Verify data classification and ensure consent/retention policies apply.",
                pattern=r"\b(email|phone|address|dob|ssn|social_security|passport)\b",
                tags=["data-inventory"],
                impact={"data_types": ["personal"]},
            ),
            PatternRule(
                rule_id="PRIV-002",
                category="privacy",
                title="PII in logs",
                description="Logging of personal data can increase exposure risk.",
                severity="high",
                confidence="medium",
                remediation="Redact PII before logging or remove logging statements.",
                pattern=r"(?i)(logger|log)\.(info|debug|warn|error).*\\b(email|phone|ssn|address)\\b",
                tags=["logging", "pii"],
                impact={"data_types": ["personal"]},
                likelihood={"reachability": "runtime_logs"},
            ),
        ]

        findings: list[FindingMatch] = []
        for path, content in context.file_contents.items():
            findings.extend(match_patterns(path, content, rules))
        return findings
