"""PR review service using high-precision analyzers only."""

import logging
import re
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pr_finding import PRFinding
from app.models.pr_review import PRReview
from app.models.repository import Repository
from app.services.github_service import GitHubService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ReviewService:
    """PR review service using high-precision analyzers only."""

    def __init__(self, db: AsyncSession, github_service: GitHubService, llm_service: LLMService):
        self.db = db
        self.github_service = github_service
        self.llm_service = llm_service
        # Analyzer will be imported when available
        self.analyzer = None

    async def review_pr(
        self,
        repo_id: str,
        pr_number: int,
        installation_id: int,
    ) -> PRReview:
        """Review a PR with high-precision analysis.

        Args:
            repo_id: Repository UUID
            pr_number: PR number
            installation_id: GitHub installation ID

        Returns:
            PRReview record
        """
        # Lazy import analyzer to avoid circular imports
        if self.analyzer is None:
            from app.analyzers.high_precision_analyzer import HighPrecisionAnalyzer, Finding, Severity

            self.analyzer = HighPrecisionAnalyzer()
            self.Finding = Finding
            self.Severity = Severity

        # Get repo
        result = await self.db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one()

        # Create review record
        review = PRReview(
            repo_id=repo_id,
            pr_number=pr_number,
            status="analyzing",
        )
        self.db.add(review)
        await self.db.flush()

        try:
            # Get PR data
            pr_data = await self.github_service.get_pr(
                installation_id=installation_id,
                owner=repo.owner,
                repo=repo.name,
                pr_number=pr_number,
            )

            review.pr_title = pr_data["title"]
            review.pr_url = pr_data["html_url"]
            review.head_sha = pr_data["head"]["sha"]
            review.base_sha = pr_data["base"]["sha"]

            # Get changed files
            pr_files = await self.github_service.get_pr_files(
                installation_id=installation_id,
                owner=repo.owner,
                repo=repo.name,
                pr_number=pr_number,
            )

            review.files_changed = len(pr_files)

            # Analyze each file
            all_findings = []

            for file_data in pr_files:
                file_path = file_data["filename"]
                status = file_data["status"]
                patch = file_data.get("patch", "")

                # Get diff lines
                diff_lines = self._parse_diff_lines(patch) if patch else None

                # For added/modified files, get content
                if status in ("added", "modified"):
                    try:
                        content = await self.github_service.get_file_content(
                            installation_id=installation_id,
                            owner=repo.owner,
                            repo=repo.name,
                            path=file_path,
                            ref=review.head_sha,
                        )

                        findings = self.analyzer.analyze_file(
                            file_path=file_path,
                            content=content,
                            diff_lines=diff_lines,
                        )
                        all_findings.extend(findings)

                    except Exception as e:
                        logger.warning(f"Failed to analyze file {file_path}: {e}")
                        continue

                # For any file, check if it's a dangerous file type
                elif status == "added":
                    findings = self.analyzer.analyze_file(
                        file_path=file_path,
                        content="",
                        diff_lines=None,
                    )
                    all_findings.extend(findings)

            # Store findings
            for finding in all_findings:
                pr_finding = PRFinding(
                    pr_review_id=review.id,
                    repo_id=repo_id,
                    severity=finding.severity.value,
                    category=finding.category.value,
                    file_path=finding.file_path,
                    start_line=finding.start_line,
                    end_line=finding.end_line,
                    evidence=finding.evidence,
                )
                self.db.add(pr_finding)

            # Generate explanations for critical findings only
            critical_findings = [f for f in all_findings if f.severity == self.Severity.CRITICAL]
            if critical_findings:
                await self._add_explanations(critical_findings)

            # Post to GitHub
            await self._post_review(repo, review, all_findings, installation_id)

            # Update stats
            review.findings_count = len(all_findings)
            review.critical_count = len(critical_findings)
            review.status = "completed"
            review.review_posted = True
            review.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"PR review failed: {e}")
            review.status = "failed"
            await self.db.commit()
            raise

        await self.db.commit()
        return review

    def _parse_diff_lines(self, patch: str) -> list[int]:
        """Parse diff to get added line numbers."""
        if not patch:
            return []

        lines = []
        current_line = 0

        for line in patch.split("\n"):
            if line.startswith("@@"):
                # Parse @@ -start,count +start,count @@
                match = re.search(r"\+(\d+)", line)
                if match:
                    current_line = int(match.group(1)) - 1
            elif line.startswith("+") and not line.startswith("+++"):
                current_line += 1
                lines.append(current_line)
            elif not line.startswith("-"):
                current_line += 1

        return lines

    async def _add_explanations(self, findings: list) -> None:
        """Add LLM explanations to critical findings."""
        for finding in findings[:5]:  # Limit to 5 explanations
            prompt = f"""Explain this security finding in 2 sentences and suggest a fix in 1 sentence.

Finding: {finding.evidence.get('reason', '')}
File: {finding.file_path}
Code: {finding.evidence.get('snippet', '')}

Be concise and actionable."""

            explanation = await self.llm_service.generate(prompt, max_tokens=150)
            finding.evidence["explanation"] = explanation

    async def _post_review(
        self,
        repo: Repository,
        review: PRReview,
        findings: list,
        installation_id: int,
    ) -> None:
        """Post review to GitHub."""
        if not findings:
            # No findings - just post a comment
            await self.github_service.create_pr_review(
                installation_id=installation_id,
                owner=repo.owner,
                repo=repo.name,
                pr_number=review.pr_number,
                body="**CodeProof Review**\n\nNo high-risk issues detected.",
                event="COMMENT",
            )
            return

        # Build summary
        critical = [f for f in findings if f.severity == self.Severity.CRITICAL]
        warnings = [f for f in findings if f.severity == self.Severity.WARNING]
        info = [f for f in findings if f.severity == self.Severity.INFO]

        body_parts = ["**CodeProof Review**\n"]

        if critical:
            body_parts.append(f"### :red_circle: Critical ({len(critical)})\n")
            for f in critical:
                body_parts.append(
                    f"- **{f.evidence.get('pattern', f.category.value)}** "
                    f"in `{f.file_path}:{f.start_line}`\n"
                )

        if warnings:
            body_parts.append(f"\n### :yellow_circle: Warnings ({len(warnings)})\n")
            for f in warnings:
                body_parts.append(
                    f"- {f.evidence.get('reason', f.category.value)} " f"in `{f.file_path}`\n"
                )

        if info:
            body_parts.append(f"\n### :blue_circle: Info ({len(info)})\n")
            body_parts.append(f"{len(info)} informational items.\n")

        body = "".join(body_parts)

        # Build inline comments for critical findings only
        comments = []
        for finding in critical[:10]:
            comment_body = (
                f"**{finding.severity.value.upper()}**: "
                f"{finding.evidence.get('pattern', finding.category.value)}\n\n"
                f"{finding.evidence.get('reason', '')}\n\n"
            )

            if finding.evidence.get("explanation"):
                comment_body += f"**Explanation:** {finding.evidence['explanation']}\n\n"

            comment_body += f"```\n{finding.evidence.get('snippet', '')[:200]}\n```"

            comments.append(
                {
                    "path": finding.file_path,
                    "line": finding.start_line,
                    "body": comment_body,
                }
            )

        # Determine event type
        event = "REQUEST_CHANGES" if critical else "COMMENT"

        # Post review
        result = await self.github_service.create_pr_review(
            installation_id=installation_id,
            owner=repo.owner,
            repo=repo.name,
            pr_number=review.pr_number,
            body=body,
            event=event,
            comments=comments if comments else None,
        )

        review.github_review_id = result.get("id")

