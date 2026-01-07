"""Prompt Studio templates for guided prompts."""


class PromptStudioService:
    """Static prompt templates for common objectives."""

    def list_templates(self) -> list[dict]:
        return [
            {
                "id": "fix-security-finding",
                "title": "Fix security finding with patch diff",
                "description": "Generate a minimal patch to remediate a security finding and add tests.",
                "prompt": (
                    "Fix the security issue described below. Provide a unified diff patch, "
                    "update tests, and explain how to verify the fix.\n\n"
                    "Finding summary:\n{{finding_summary}}\n\n"
                    "Evidence:\n{{evidence}}\n\n"
                    "Constraints:\n- Keep changes minimal\n- Do not change public APIs\n- No secrets in output"
                ),
                "acceptance_criteria": [
                    "Patch removes the risky pattern",
                    "Tests cover the failure mode",
                    "All existing tests pass",
                ],
                "safety_constraints": [
                    "Do not log or print secrets",
                    "Avoid breaking schema changes",
                    "Preserve existing behavior where possible",
                ],
            },
            {
                "id": "reliability-retries-timeouts",
                "title": "Improve reliability with retries/timeouts",
                "description": "Add timeouts and retries for outbound calls with safe defaults.",
                "prompt": (
                    "Add timeouts and retries for outbound calls in the module below. "
                    "Use a safe retry policy and document the behavior.\n\n"
                    "Target module:\n{{module_path}}\n\n"
                    "Constraints:\n- Do not change public APIs\n- Keep defaults conservative"
                ),
                "acceptance_criteria": [
                    "Outbound requests have explicit timeouts",
                    "Retry policy avoids retrying on 4xx",
                    "Behavior documented in code/comments",
                ],
                "safety_constraints": [
                    "No infinite retries",
                    "Do not break idempotency",
                ],
            },
            {
                "id": "consent-gating-analytics",
                "title": "Add consent gating for analytics",
                "description": "Add consent checks and consent logging for analytics events.",
                "prompt": (
                    "Add consent gating for analytics. Only send events when user consent is granted. "
                    "Introduce a consent log model if needed.\n\n"
                    "Relevant files:\n{{related_files}}\n\n"
                    "Constraints:\n- Default to no tracking without explicit consent\n- Add tests"
                ),
                "acceptance_criteria": [
                    "Analytics events are gated by consent",
                    "Consent changes are logged",
                    "Tests cover consent on/off flows",
                ],
                "safety_constraints": [
                    "Do not transmit personal data without consent",
                    "Keep backward compatibility where possible",
                ],
            },
        ]
