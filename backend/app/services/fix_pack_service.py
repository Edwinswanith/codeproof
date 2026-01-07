"""Fix pack generation service."""

from __future__ import annotations

from typing import Any

from app.models.scan import Finding, ScanRun


class FixPackService:
    """Generate fix packs and prompt packs from findings."""

    DEFAULT_CONSTRAINTS = [
        "Do not change public API signatures unless explicitly allowed",
        "Do not introduce breaking schema migrations without a plan",
        "Keep changes minimal and include tests",
        "No secrets in output",
    ]

    def build_prompt_pack(
        self,
        scan_run: ScanRun,
        findings: list[Finding],
        target_tool: str,
        constraints: list[str] | None = None,
    ) -> dict[str, Any]:
        repo = scan_run.repo
        constraints_list = constraints or self.DEFAULT_CONSTRAINTS
        summary = "; ".join(f"{f.title} ({f.severity})" for f in findings)
        evidence = []
        for finding in findings:
            for instance in finding.instances:
                snippet = instance.evidence_snippet
                file_path = instance.evidence_snippet.file_snapshot.path
                evidence.append(
                    {
                        "file": file_path,
                        "start_line": snippet.start_line,
                        "end_line": snippet.end_line,
                        "snippet": snippet.snippet_text,
                    }
                )

        prompt_lines = [
            "You are an expert software engineer.",
            "Fix the following finding(s) with minimal, safe changes.",
            "",
            f"Repository: {repo.full_name if repo else 'unknown'}",
            f"Commit SHA: {scan_run.commit_sha}",
            "",
            "Findings:",
            summary,
            "",
            "Evidence:",
            *[f"- {e['file']}:{e['start_line']}-{e['end_line']}" for e in evidence],
            "",
            "Constraints:",
            *[f"- {c}" for c in constraints_list],
            "",
            "Deliverables:",
            "- Unified diff patch",
            "- Updated/added tests if applicable",
            "- Short explanation of changes",
            "- How to verify locally",
        ]

        return {
            "target_tool": target_tool,
            "system_context": {
                "repo": {
                    "name": repo.full_name if repo else "",
                    "commit_sha": scan_run.commit_sha,
                    "primary_languages": [],
                },
                "constraints": constraints_list,
            },
            "inputs": {
                "finding_summary": summary,
                "evidence": evidence,
                "related_files": sorted({e["file"] for e in evidence}),
                "acceptance_criteria": [
                    "New unit tests cover the failure mode",
                    "All existing tests pass",
                    "Fix removes the finding trigger without reducing coverage",
                ],
            },
            "prompt": "\n".join(prompt_lines),
            "expected_output": [
                "Unified diff patch",
                "Test updates",
                "Short explanation of changes",
                "How to verify locally",
            ],
        }

    def build_human_explanation(self, findings: list[Finding]) -> str:
        if not findings:
            return "No findings selected."
        lines = []
        for finding in findings:
            lines.append(f"- {finding.title}: {finding.description or ''}".strip())
        return "\n".join(lines)
