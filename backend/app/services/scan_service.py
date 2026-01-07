"""Scan service for repo intelligence."""

import hashlib
import logging
import os
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzers import (
    ArchitectureAnalyzer,
    AnalyzerContext,
    MaintainabilityAnalyzer,
    PerformanceAnalyzer,
    PrivacyAnalyzer,
    ReliabilityAnalyzer,
    SecurityAnalyzer,
)
from app.models.repository import Repository
from app.models.scan import (
    ControlFramework,
    ControlResult,
    CoverageSummary,
    EvidenceSnippet,
    FileSnapshot,
    Finding,
    FindingInstance,
    FixPack,
    ScanRun,
)
from app.services.clone_service import CloneService
from app.services.coverage_service import CoverageService
from app.services.evidence_service import EvidenceService
from app.services.parser_service import ParserService, TREE_SITTER_AVAILABLE

logger = logging.getLogger(__name__)


class ScanService:
    """Orchestrates repo scans, analyzers, and persistence."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.clone_service = CloneService()
        self.parser_service = ParserService()
        self.coverage_service = CoverageService()
        self.evidence_service = EvidenceService()
        self.analyzers = [
            SecurityAnalyzer(),
            PrivacyAnalyzer(),
            ReliabilityAnalyzer(),
            PerformanceAnalyzer(),
            MaintainabilityAnalyzer(),
            ArchitectureAnalyzer(),
        ]

    def build_config_hash(self, config: dict[str, Any]) -> str:
        import json

        normalized = json.dumps(config or {}, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def resolve_repo(self, repo_url: str | None, repo_id, user_id) -> Repository:
        if repo_id:
            result = await self.db.execute(select(Repository).where(Repository.id == repo_id))
            repo = result.scalar_one_or_none()
            if repo and repo.user_id == user_id:
                return repo
            raise ValueError("Repository not found")

        if not repo_url:
            raise ValueError("repo_url or repo_id is required")

        owner, name = self.clone_service._parse_github_url(repo_url)
        full_name = f"{owner}/{name}"

        existing = await self.db.execute(
            select(Repository).where(
                Repository.user_id == user_id,
                Repository.full_name == full_name,
            )
        )
        repo = existing.scalar_one_or_none()
        if repo:
            return repo

        # Create lightweight repo record for public URL scans
        repo_hash = int(hashlib.sha256(full_name.encode("utf-8")).hexdigest()[:12], 16)
        repo = Repository(
            user_id=user_id,
            github_repo_id=repo_hash,
            github_installation_id=0,
            owner=owner,
            name=name,
            full_name=full_name,
            private=False,
            default_branch="main",
            index_status="ready",
        )
        self.db.add(repo)
        await self.db.commit()
        await self.db.refresh(repo)
        return repo

    async def create_scan_run(
        self,
        repo: Repository,
        commit_sha: str,
        ref: str | None,
        config: dict[str, Any],
    ) -> tuple[ScanRun, bool]:
        config_hash = self.build_config_hash(config)
        existing = await self.db.execute(
            select(ScanRun).where(
                ScanRun.repo_id == repo.id,
                ScanRun.commit_sha == commit_sha,
                ScanRun.config_hash == config_hash,
            )
        )
        scan_run = existing.scalar_one_or_none()
        if scan_run:
            return scan_run, False

        scan_run = ScanRun(
            repo_id=repo.id,
            commit_sha=commit_sha,
            ref=ref,
            status="queued",
            config=config,
            config_hash=config_hash,
        )
        self.db.add(scan_run)
        await self.db.commit()
        await self.db.refresh(scan_run)
        return scan_run, True

    async def run_scan(
        self,
        scan_run_id: str,
        repo_url: str,
        ref: str | None,
        token: str | None,
    ) -> None:
        scan_run = await self._get_scan_run(scan_run_id)
        scan_run.status = "running"
        scan_run.started_at = datetime.utcnow()
        await self.db.commit()

        clone_path = None
        try:
            clone_path, commit_sha = await self.clone_service.clone_repo(
                repo_url=repo_url,
                branch=ref,
                token=token,
            )
            scan_run.commit_sha = commit_sha
            if ref and not scan_run.ref:
                scan_run.ref = ref
            await self.db.commit()

            self.coverage_service.reset()
            self.coverage_service.discover_files(clone_path)
            parse_result = self.parser_service.parse_repository(
                clone_path,
                coverage_service=self.coverage_service,
            )
            coverage_report = self.coverage_service.compute_coverage()

            degraded_modes = []
            if not TREE_SITTER_AVAILABLE:
                degraded_modes.append("tree_sitter_unavailable")
            if coverage_report.is_incomplete:
                degraded_modes.append("low_coverage")
            if coverage_report.parse_errors:
                degraded_modes.append("parse_errors")

            file_contents = self._load_file_contents(clone_path)
            file_snapshot_map = await self._store_file_snapshots(scan_run, file_contents)

            context = AnalyzerContext(
                repo_path=clone_path,
                file_contents=file_contents,
                parse_result=parse_result,
                coverage_report=coverage_report,
            )

            enabled = set((scan_run.config or {}).get("analyzers_enabled") or [])
            matches = []
            for analyzer in self.analyzers:
                if enabled and analyzer.name not in enabled:
                    continue
                self.coverage_service.record_analyzer_run(analyzer.name)
                matches.extend(analyzer.analyze(context))

            await self._store_findings(scan_run, matches, file_snapshot_map, file_contents, coverage_report)
            await self._store_coverage(scan_run, coverage_report, degraded_modes)
            await self._store_control_results(scan_run, matches)

            scan_run.status = "degraded" if degraded_modes else "completed"
            scan_run.finished_at = datetime.utcnow()
            await self.db.commit()
        except Exception as exc:
            logger.exception("Scan failed: %s", exc)
            scan_run.status = "failed"
            scan_run.finished_at = datetime.utcnow()
            await self.db.commit()
            raise
        finally:
            if clone_path:
                self.clone_service.cleanup(clone_path)

    async def _get_scan_run(self, scan_run_id: str) -> ScanRun:
        result = await self.db.execute(select(ScanRun).where(ScanRun.id == scan_run_id))
        scan_run = result.scalar_one_or_none()
        if not scan_run:
            raise ValueError("Scan run not found")
        return scan_run

    def _load_file_contents(self, repo_path: str) -> dict[str, str]:
        file_contents: dict[str, str] = {}
        for file_path in self.coverage_service.files_discovered:
            full_path = os.path.join(repo_path, file_path)
            try:
                file_size = os.path.getsize(full_path)
            except OSError:
                continue

            skip_reason = self.coverage_service.should_skip_file(file_path, file_size)
            if skip_reason in {"binary", "vendor_or_build_dir", "too_large", "minified_or_bundle"}:
                continue

            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as handle:
                    file_contents[file_path] = handle.read()
            except Exception:
                continue
        return file_contents

    async def _store_file_snapshots(
        self, scan_run: ScanRun, file_contents: dict[str, str]
    ) -> dict[str, FileSnapshot]:
        snapshot_map: dict[str, FileSnapshot] = {}
        for path, content in file_contents.items():
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            ext = os.path.splitext(path)[1].lower()
            language = self.parser_service.SUPPORTED_LANGUAGES.get(ext)
            snapshot = FileSnapshot(
                scan_run_id=scan_run.id,
                path=path,
                language=language,
                content_hash=content_hash,
                size_bytes=len(content.encode("utf-8")),
                is_binary=False,
                stored_at=f"sha256:{content_hash}",
            )
            self.db.add(snapshot)
            await self.db.flush()
            snapshot_map[path] = snapshot
        await self.db.commit()
        return snapshot_map

    async def _store_findings(
        self,
        scan_run: ScanRun,
        matches: list[Any],
        file_snapshot_map: dict[str, FileSnapshot],
        file_contents: dict[str, str],
        coverage_report: Any,
    ) -> None:
        dedupe_map: dict[str, Finding] = {}
        for match in matches:
            adjusted_confidence = self._adjust_confidence(match.confidence, coverage_report)
            dedupe_key = self._dedupe_key(match)
            finding = dedupe_map.get(dedupe_key)
            if not finding:
                confidence_rationale = {
                    "evidence_strength": "direct" if adjusted_confidence in {"high", "medium"} else "heuristic",
                    "trace_strength": "none",
                    "coverage_factor": round(coverage_report.coverage_percentage / 100, 2),
                    "verification_factor": 0.0,
                }
                finding = Finding(
                    scan_run_id=scan_run.id,
                    category=match.category,
                    rule_id=match.rule_id,
                    title=match.title,
                    description=match.description,
                    severity=match.severity,
                    confidence=adjusted_confidence,
                    confidence_rationale=confidence_rationale,
                    impact=match.impact or {},
                    likelihood=match.likelihood or {},
                    remediation_summary=match.remediation,
                    tags=match.tags,
                    dedupe_key=dedupe_key,
                )
                self.db.add(finding)
                await self.db.flush()
                dedupe_map[dedupe_key] = finding

            snapshot = file_snapshot_map.get(match.file_path)
            if not snapshot:
                continue
            content = file_contents.get(match.file_path, "")
            snippet_text, context_before, context_after = self.evidence_service.extract_snippet(
                content, match.start_line, match.end_line
            )
            snippet_hash = self.evidence_service.hash_snippet(snippet_text)
            evidence = EvidenceSnippet(
                file_snapshot_id=snapshot.id,
                start_line=match.start_line,
                end_line=match.end_line,
                snippet_text=snippet_text,
                snippet_hash=snippet_hash,
                context_before_lines=context_before,
                context_after_lines=context_after,
            )
            self.db.add(evidence)
            await self.db.flush()

            instance = FindingInstance(
                finding_id=finding.id,
                evidence_snippet_id=evidence.id,
                symbol_id=None,
                source_to_sink_trace_id=None,
                retrieval_score=None,
            )
            self.db.add(instance)

        await self.db.commit()

    async def _store_coverage(self, scan_run: ScanRun, coverage_report: Any, degraded_modes: list[str]) -> None:
        ast_success_rate = round(coverage_report.coverage_percentage / 100, 3)
        summary = CoverageSummary(
            scan_run_id=scan_run.id,
            total_files=coverage_report.total_files_discovered,
            parsed_files=coverage_report.files_parsed_successfully,
            skipped_files=sum(coverage_report.files_skipped.values()),
            skipped_reasons=coverage_report.files_skipped,
            languages=coverage_report.languages_detected,
            ast_success_rate=ast_success_rate,
            degraded_modes=degraded_modes,
            parse_errors_count=coverage_report.files_failed_parsing,
            parse_errors=coverage_report.parse_errors,
            coverage_percentage=coverage_report.coverage_percentage,
        )
        self.db.add(summary)
        await self.db.commit()

    async def _store_control_results(self, scan_run: ScanRun, matches: list[Any]) -> None:
        framework = await self._ensure_default_framework(scan_run.config)
        control_results = []
        for control in framework.controls:
            control_id = control.get("id", "unknown")
            status = "unknown"
            rationale = "No evidence available."
            evidence_ids: list[str] = []
            for match in matches:
                if control_id in (match.rule_id, match.category):
                    status = "fail"
                    rationale = "Finding mapped to control."
                    break
            control_results.append(
                ControlResult(
                    scan_run_id=scan_run.id,
                    control_framework_id=framework.id,
                    control_id=control_id,
                    status=status,
                    evidence_instance_ids=evidence_ids,
                    rationale=rationale,
                )
            )
        self.db.add_all(control_results)
        await self.db.commit()

    async def _ensure_default_framework(self, config: dict[str, Any]) -> ControlFramework:
        region = (config or {}).get("region") or "global"
        sector = (config or {}).get("sector")
        result = await self.db.execute(
            select(ControlFramework).where(
                ControlFramework.region == region,
                ControlFramework.sector == sector,
            )
        )
        framework = result.scalar_one_or_none()
        if framework:
            return framework
        framework = ControlFramework(
            name="Baseline Controls",
            region=region,
            sector=sector,
            version="v1",
            controls=[
                {"id": "privacy.consent", "name": "Consent gating for analytics"},
                {"id": "security.secrets", "name": "Secrets are not hard-coded"},
                {"id": "reliability.timeouts", "name": "Outbound calls use timeouts"},
            ],
        )
        self.db.add(framework)
        await self.db.commit()
        await self.db.refresh(framework)
        return framework

    def _dedupe_key(self, match: Any) -> str:
        normalized_path = os.path.dirname(match.file_path)
        parts = [
            match.rule_id,
            match.normalized_sink or "",
            match.normalized_source or "",
            match.symbol or "",
            normalized_path,
        ]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    def _adjust_confidence(self, confidence: str, coverage_report: Any) -> str:
        downgrade = {"high": "medium", "medium": "low", "low": "unknown", "unknown": "unknown"}
        adjusted = confidence
        if coverage_report.coverage_percentage < 80:
            adjusted = downgrade.get(adjusted, adjusted)
        if not TREE_SITTER_AVAILABLE:
            adjusted = downgrade.get(adjusted, adjusted)
        return adjusted
