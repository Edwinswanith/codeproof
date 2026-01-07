"""Repo intelligence scan routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models.repository import Repository
from app.models.scan import (
    ControlResult,
    EvidenceSnippet,
    FileSnapshot,
    Finding,
    FindingInstance,
    FixPack,
    ScanRun,
)
from app.schemas.intelligence import (
    EvidenceSnippetResponse,
    FindingDetailResponse,
    FindingInstanceResponse,
    FindingResponse,
    FindingsListResponse,
    ControlResultsResponse,
    FixPackRequest,
    FixPackResponse,
    PromptTemplateResponse,
    ScanRequest,
    ScanRunListResponse,
    ScanRunResponse,
    ScanRunStatusResponse,
)
from app.services.fix_pack_service import FixPackService
from app.services.prompt_studio_service import PromptStudioService
from app.services.scan_service import ScanService
from app.tasks.scan_repo import scan_repository

router = APIRouter()


@router.post("/repos/scan", response_model=ScanRunStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_scan(
    scan_request: ScanRequest,
    user: CurrentUser,
    db: DbSession,
):
    """Queue a scan run for a repository."""
    scan_service = ScanService(db)
    try:
        repo = await scan_service.resolve_repo(
            repo_url=scan_request.repo_url,
            repo_id=scan_request.repo_id,
            user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    repo_url = scan_request.repo_url or f"https://github.com/{repo.full_name}.git"
    config = {
        "region": scan_request.region,
        "sector": scan_request.sector,
        "analyzers_enabled": scan_request.analyzers_enabled,
        "max_files": scan_request.max_files,
        "skip_vendor": scan_request.skip_vendor,
    }
    commit_hint = scan_request.ref or "pending"

    scan_run, created = await scan_service.create_scan_run(
        repo, commit_hint, scan_request.ref, config
    )
    if created and scan_run.status == "queued":
        scan_repository.delay(str(scan_run.id), repo_url, scan_request.ref)

    return ScanRunStatusResponse(scan_run=ScanRunResponse.model_validate(scan_run))


@router.get("/scan_runs/{scan_run_id}", response_model=ScanRunStatusResponse)
async def get_scan_run(scan_run_id: UUID, user: CurrentUser, db: DbSession):
    """Get scan run status and coverage."""
    result = await db.execute(
        select(ScanRun)
        .join(Repository, Repository.id == ScanRun.repo_id)
        .options(selectinload(ScanRun.coverage_summary))
        .where(ScanRun.id == scan_run_id)
        .where(Repository.user_id == user.id)
    )
    scan_run = result.scalar_one_or_none()
    if not scan_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan run not found")

    return ScanRunStatusResponse(scan_run=ScanRunResponse.model_validate(scan_run))


@router.get("/repos/{repo_id}/scan_runs", response_model=ScanRunListResponse)
async def list_scan_runs(repo_id: UUID, user: CurrentUser, db: DbSession):
    """List scan runs for a repository."""
    result = await db.execute(
        select(ScanRun)
        .join(Repository, Repository.id == ScanRun.repo_id)
        .options(selectinload(ScanRun.coverage_summary))
        .where(ScanRun.repo_id == repo_id)
        .where(Repository.user_id == user.id)
        .order_by(ScanRun.created_at.desc())
    )
    scan_runs = result.scalars().all()
    return ScanRunListResponse(
        scan_runs=[ScanRunResponse.model_validate(run) for run in scan_runs],
        total=len(scan_runs),
    )


@router.get("/scan_runs/{scan_run_id}/findings", response_model=FindingsListResponse)
async def list_findings(
    scan_run_id: UUID,
    user: CurrentUser,
    db: DbSession,
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    confidence: str | None = Query(default=None),
):
    """List findings with filters and counts."""
    stmt = (
        select(Finding, func.count(FindingInstance.id))
        .outerjoin(FindingInstance, FindingInstance.finding_id == Finding.id)
        .join(ScanRun, ScanRun.id == Finding.scan_run_id)
        .join(Repository, Repository.id == ScanRun.repo_id)
        .where(Finding.scan_run_id == scan_run_id)
        .where(Repository.user_id == user.id)
        .group_by(Finding.id)
    )
    if category:
        stmt = stmt.where(Finding.category == category)
    if severity:
        stmt = stmt.where(Finding.severity == severity)
    if confidence:
        stmt = stmt.where(Finding.confidence == confidence)

    result = await db.execute(stmt)
    rows = result.all()

    findings = []
    for finding, instance_count in rows:
        item = FindingResponse.model_validate(finding)
        item.instance_count = instance_count
        findings.append(item)

    counts_by_category = await _count_by_field(db, scan_run_id, user.id, Finding.category)
    counts_by_severity = await _count_by_field(db, scan_run_id, user.id, Finding.severity)
    counts_by_confidence = await _count_by_field(db, scan_run_id, user.id, Finding.confidence)

    return FindingsListResponse(
        findings=findings,
        total=len(findings),
        counts_by_category=counts_by_category,
        counts_by_severity=counts_by_severity,
        counts_by_confidence=counts_by_confidence,
    )


@router.get("/scan_runs/{scan_run_id}/controls", response_model=ControlResultsResponse)
async def list_controls(scan_run_id: UUID, user: CurrentUser, db: DbSession):
    """List control results for a scan run."""
    result = await db.execute(
        select(ControlResult)
        .join(ScanRun, ScanRun.id == ControlResult.scan_run_id)
        .join(Repository, Repository.id == ScanRun.repo_id)
        .where(ControlResult.scan_run_id == scan_run_id)
        .where(Repository.user_id == user.id)
        .order_by(ControlResult.control_id.asc())
    )
    controls = result.scalars().all()
    return ControlResultsResponse(
        controls=[
            {
                "id": c.id,
                "control_id": c.control_id,
                "status": c.status,
                "evidence_instance_ids": c.evidence_instance_ids,
                "rationale": c.rationale,
            }
            for c in controls
        ],
        total=len(controls),
    )


@router.get("/findings/{finding_id}", response_model=FindingDetailResponse)
async def get_finding(finding_id: UUID, user: CurrentUser, db: DbSession):
    """Get full finding details including evidence."""
    result = await db.execute(
        select(Finding)
        .join(ScanRun, ScanRun.id == Finding.scan_run_id)
        .join(Repository, Repository.id == ScanRun.repo_id)
        .options(
            selectinload(Finding.instances)
            .selectinload(FindingInstance.evidence_snippet)
            .selectinload(EvidenceSnippet.file_snapshot),
        )
        .where(Finding.id == finding_id)
        .where(Repository.user_id == user.id)
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    response = FindingDetailResponse.model_validate(finding)
    response.instances = [_serialize_instance(instance) for instance in finding.instances]
    response.instance_count = len(response.instances)
    return response


@router.post("/fix_packs", response_model=FixPackResponse, status_code=status.HTTP_201_CREATED)
async def create_fix_pack(
    request: FixPackRequest,
    user: CurrentUser,
    db: DbSession,
):
    """Generate a fix pack for selected findings."""
    result = await db.execute(
        select(ScanRun)
        .join(Repository, Repository.id == ScanRun.repo_id)
        .options(selectinload(ScanRun.repo))
        .where(ScanRun.id == request.scan_run_id)
        .where(Repository.user_id == user.id)
    )
    scan_run = result.scalar_one_or_none()
    if not scan_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan run not found")

    finding_rows = await db.execute(
        select(Finding)
        .options(
            selectinload(Finding.instances)
            .selectinload(FindingInstance.evidence_snippet)
            .selectinload(EvidenceSnippet.file_snapshot)
        )
        .where(Finding.id.in_(request.finding_ids))
        .where(Finding.scan_run_id == scan_run.id)
    )
    findings = finding_rows.scalars().all()
    if not findings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Findings not found")

    fix_pack_service = FixPackService()
    prompt_pack = fix_pack_service.build_prompt_pack(
        scan_run=scan_run,
        findings=findings,
        target_tool=request.target_tool,
        constraints=request.constraints,
    )
    human_explanation = fix_pack_service.build_human_explanation(findings)

    fix_pack = FixPack(
        scan_run_id=scan_run.id,
        title="Fix Pack",
        objective="Resolve selected findings",
        scope="multi_finding" if len(findings) > 1 else "single_finding",
        finding_ids=[str(f.id) for f in findings],
        human_explanation=human_explanation,
        prompt_pack=prompt_pack,
        verification_checklist=prompt_pack["inputs"]["acceptance_criteria"],
        suggested_patch=None,
        risks_and_tradeoffs={},
    )
    db.add(fix_pack)
    await db.commit()
    await db.refresh(fix_pack)

    return FixPackResponse.model_validate(fix_pack)


@router.get("/fix_packs/{fix_pack_id}", response_model=FixPackResponse)
async def get_fix_pack(fix_pack_id: UUID, user: CurrentUser, db: DbSession):
    """Fetch fix pack details."""
    result = await db.execute(
        select(FixPack)
        .join(ScanRun, ScanRun.id == FixPack.scan_run_id)
        .join(Repository, Repository.id == ScanRun.repo_id)
        .where(FixPack.id == fix_pack_id)
        .where(Repository.user_id == user.id)
    )
    fix_pack = result.scalar_one_or_none()
    if not fix_pack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fix pack not found")
    return FixPackResponse.model_validate(fix_pack)


@router.get("/prompt_studio/templates", response_model=list[PromptTemplateResponse])
async def list_prompt_templates(user: CurrentUser):
    """List Prompt Studio templates."""
    service = PromptStudioService()
    return [PromptTemplateResponse(**template) for template in service.list_templates()]


async def _count_by_field(db: DbSession, scan_run_id: UUID, user_id: UUID, field) -> dict[str, int]:
    result = await db.execute(
        select(field, func.count(Finding.id))
        .join(ScanRun, ScanRun.id == Finding.scan_run_id)
        .join(Repository, Repository.id == ScanRun.repo_id)
        .where(Finding.scan_run_id == scan_run_id)
        .where(Repository.user_id == user_id)
        .group_by(field)
    )
    return {row[0]: row[1] for row in result.all() if row[0]}


def _serialize_instance(instance: FindingInstance) -> FindingInstanceResponse:
    snippet = instance.evidence_snippet
    file_path = snippet.file_snapshot.path if snippet.file_snapshot else ""
    evidence = EvidenceSnippetResponse(
        id=snippet.id,
        file_path=file_path,
        start_line=snippet.start_line,
        end_line=snippet.end_line,
        snippet_text=snippet.snippet_text,
        snippet_hash=snippet.snippet_hash,
        context_before_lines=snippet.context_before_lines,
        context_after_lines=snippet.context_after_lines,
    )
    return FindingInstanceResponse(
        id=instance.id,
        evidence=evidence,
        symbol_id=instance.symbol_id,
        source_to_sink_trace_id=instance.source_to_sink_trace_id,
        retrieval_score=instance.retrieval_score,
        instance_severity_override=instance.instance_severity_override,
        instance_confidence_override=instance.instance_confidence_override,
    )
