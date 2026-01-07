"""Maintainability analyzer for complexity hotspots."""

from app.analyzers.base import Analyzer, AnalyzerContext, FindingMatch


class MaintainabilityAnalyzer(Analyzer):
    name = "maintainability"

    def __init__(self, max_function_lines: int = 80) -> None:
        self.max_function_lines = max_function_lines

    def analyze(self, context: AnalyzerContext) -> list[FindingMatch]:
        findings: list[FindingMatch] = []
        parse_result = context.parse_result
        if not parse_result:
            return findings

        for symbol in parse_result.symbols:
            if symbol.type not in {"function", "method"}:
                continue
            line_count = symbol.line_end - symbol.line_start + 1
            if line_count < self.max_function_lines:
                continue
            snippet_lines = (symbol.body or "").splitlines()[:6]
            snippet = "\n".join(snippet_lines)
            findings.append(
                FindingMatch(
                    rule_id="MAINT-001",
                    category="maintainability",
                    title="Large function detected",
                    description=f"Function exceeds {self.max_function_lines} lines, increasing complexity.",
                    severity="medium",
                    confidence="medium",
                    remediation="Refactor into smaller functions with clear responsibilities.",
                    tags=["complexity", "refactor"],
                    file_path=symbol.file_path,
                    start_line=symbol.line_start,
                    end_line=symbol.line_end,
                    snippet=snippet,
                    symbol=symbol.qualified_name,
                )
            )
        return findings
