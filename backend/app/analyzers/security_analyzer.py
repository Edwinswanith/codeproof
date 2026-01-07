"""Security analyzer with deterministic pattern checks."""

from app.analyzers.base import Analyzer, AnalyzerContext, FindingMatch
from app.analyzers.patterns import PatternRule, match_patterns


class SecurityAnalyzer(Analyzer):
    name = "security"

    def analyze(self, context: AnalyzerContext) -> list[FindingMatch]:
        rules = [
            PatternRule(
                rule_id="SEC-001",
                category="security",
                title="Dynamic code execution detected",
                description="Use of eval/exec introduces code injection risk when inputs are not strictly controlled.",
                severity="high",
                confidence="medium",
                remediation="Avoid eval/exec; prefer safe parsing or explicit dispatch tables.",
                pattern=r"\b(eval|exec)\s*\(",
                tags=["injection", "code-exec"],
                likelihood={"exploitability": "depends_on_input_source"},
            ),
            PatternRule(
                rule_id="SEC-002",
                category="security",
                title="Shell execution detected",
                description="Shell command execution can be dangerous if inputs are user-controlled.",
                severity="medium",
                confidence="medium",
                remediation="Avoid shell=True; use subprocess with argument lists and strict allowlists.",
                pattern=r"\b(os\.system|subprocess\.Popen|subprocess\.run)\s*\(",
                tags=["command-exec"],
            ),
            PatternRule(
                rule_id="SEC-003",
                category="security",
                title="Potential secret in source",
                description="Hard-coded secrets in source code increase exposure risk.",
                severity="high",
                confidence="low",
                remediation="Move secrets to a secret manager or environment variables.",
                pattern=r"(?i)(api_key|secret|token|password)\s*=\s*[\"'][^\"']{8,}[\"']",
                tags=["secrets"],
            ),
        ]

        findings: list[FindingMatch] = []
        for path, content in context.file_contents.items():
            findings.extend(match_patterns(path, content, rules))
        return findings
