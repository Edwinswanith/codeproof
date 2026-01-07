"""Reliability analyzer for timeouts and idempotency signals."""

from app.analyzers.base import Analyzer, AnalyzerContext, FindingMatch


class ReliabilityAnalyzer(Analyzer):
    name = "reliability"

    def analyze(self, context: AnalyzerContext) -> list[FindingMatch]:
        findings: list[FindingMatch] = []
        for path, content in context.file_contents.items():
            lines = content.splitlines()
            for idx, line in enumerate(lines, start=1):
                if "requests." in line and "(" in line and "timeout=" not in line:
                    findings.append(
                        FindingMatch(
                            rule_id="REL-001",
                            category="reliability",
                            title="Outbound request without timeout",
                            description="Requests without timeouts can hang and exhaust workers.",
                            severity="medium",
                            confidence="medium",
                            remediation="Set explicit timeouts on outbound requests.",
                            tags=["timeouts", "outbound"],
                            file_path=path,
                            start_line=idx,
                            end_line=idx,
                            snippet=line.strip(),
                            likelihood={"reachability": "runtime_network"},
                        )
                    )
        return findings
