"""Architecture analyzer for boundary violations."""

from app.analyzers.base import Analyzer, AnalyzerContext, FindingMatch


class ArchitectureAnalyzer(Analyzer):
    name = "architecture"

    def analyze(self, context: AnalyzerContext) -> list[FindingMatch]:
        findings: list[FindingMatch] = []
        for path, content in context.file_contents.items():
            lower_path = path.lower()
            if not any(part in lower_path for part in ("routes", "controllers", "handlers")):
                continue
            if any(marker in content for marker in ("SELECT ", "session.execute", "db.", "cursor.")):
                findings.append(
                    FindingMatch(
                        rule_id="ARCH-001",
                        category="architecture",
                        title="Data access in controller layer",
                        description="Controller layer appears to access persistence directly.",
                        severity="low",
                        confidence="low",
                        remediation="Move data access to a service/repository layer.",
                        tags=["layering"],
                        file_path=path,
                        start_line=1,
                        end_line=1,
                        snippet=content.splitlines()[0] if content else "",
                    )
                )
        return findings
