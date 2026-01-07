"""Performance analyzer for query and payload signals."""

from app.analyzers.base import Analyzer, AnalyzerContext, FindingMatch
from app.analyzers.patterns import PatternRule, match_patterns


class PerformanceAnalyzer(Analyzer):
    name = "performance"

    def analyze(self, context: AnalyzerContext) -> list[FindingMatch]:
        rules = [
            PatternRule(
                rule_id="PERF-001",
                category="performance",
                title="SELECT * usage detected",
                description="SELECT * can fetch unnecessary columns and increase payload size.",
                severity="low",
                confidence="medium",
                remediation="Select only required columns and add indexes where needed.",
                pattern=r"SELECT\\s+\\*",
                tags=["sql", "payload"],
            ),
            PatternRule(
                rule_id="PERF-002",
                category="performance",
                title="Potential blocking I/O in request path",
                description="Synchronous file or network access on request paths can degrade latency.",
                severity="medium",
                confidence="low",
                remediation="Move blocking work to background jobs or use async APIs.",
                pattern=r"\\b(open|read|write)\\(|\\btime\\.sleep\\(",
                tags=["blocking-io"],
            ),
        ]

        findings: list[FindingMatch] = []
        for path, content in context.file_contents.items():
            findings.extend(match_patterns(path, content, rules))
        return findings
