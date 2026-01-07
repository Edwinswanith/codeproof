"""Schemas for repo intelligence scans, findings, and fix packs."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    """Request to start a scan."""

    repo_url: str | None = Field(default=None, description="Public GitHub URL")
    repo_id: UUID | None = Field(default=None, description="Connected repository ID")
    ref: str | None = Field(default=None, description="Branch, tag, or commit SHA")
    region: str | None = None
    sector: str | None = None
    analyzers_enabled: list[str] | None = None
    max_files: int | None = None
    skip_vendor: bool | None = True


class CoverageSummaryResponse(BaseModel):
    total_files: int
    parsed_files: int
    skipped_files: int
    skipped_reasons: dict[str, int]
    languages: dict[str, int]
    ast_success_rate: float
    degraded_modes: list[str]
    parse_errors_count: int
    parse_errors: list[str]
    coverage_percentage: float

    class Config:
        from_attributes = True


class ScanRunResponse(BaseModel):
    id: UUID
    repo_id: UUID
    commit_sha: str
    ref: str | None
    status: str
    config: dict[str, Any]
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    coverage_summary: CoverageSummaryResponse | None = None

    class Config:
        from_attributes = True


class ScanRunStatusResponse(BaseModel):
    scan_run: ScanRunResponse


class ScanRunListResponse(BaseModel):
    scan_runs: list[ScanRunResponse]
    total: int


class EvidenceSnippetResponse(BaseModel):
    id: UUID
    file_path: str
    start_line: int
    end_line: int
    snippet_text: str
    snippet_hash: str
    context_before_lines: str | None
    context_after_lines: str | None


class FindingInstanceResponse(BaseModel):
    id: UUID
    evidence: EvidenceSnippetResponse
    symbol_id: UUID | None
    source_to_sink_trace_id: UUID | None
    retrieval_score: float | None
    instance_severity_override: str | None
    instance_confidence_override: str | None


class FindingResponse(BaseModel):
    id: UUID
    scan_run_id: UUID
    category: str
    rule_id: str
    title: str
    description: str | None
    severity: str
    confidence: str
    confidence_rationale: dict[str, Any]
    impact: dict[str, Any]
    likelihood: dict[str, Any]
    remediation_summary: str | None
    tags: list[str]
    dedupe_key: str
    created_at: datetime
    instance_count: int = 0

    class Config:
        from_attributes = True


class FindingDetailResponse(FindingResponse):
    instances: list[FindingInstanceResponse]


class FindingsListResponse(BaseModel):
    findings: list[FindingResponse]
    total: int
    counts_by_category: dict[str, int] = Field(default_factory=dict)
    counts_by_severity: dict[str, int] = Field(default_factory=dict)
    counts_by_confidence: dict[str, int] = Field(default_factory=dict)


class ControlResultResponse(BaseModel):
    id: UUID
    control_id: str
    status: str
    evidence_instance_ids: list[UUID]
    rationale: str | None


class ControlResultsResponse(BaseModel):
    controls: list[ControlResultResponse]
    total: int


class PromptPackResponse(BaseModel):
    target_tool: str
    system_context: dict[str, Any]
    inputs: dict[str, Any]
    prompt: str
    expected_output: list[str]


class FixPackRequest(BaseModel):
    scan_run_id: UUID
    finding_ids: list[UUID]
    target_tool: str = Field(default="generic")
    constraints: list[str] | None = None


class FixPackResponse(BaseModel):
    id: UUID
    scan_run_id: UUID
    title: str
    objective: str | None
    scope: str
    finding_ids: list[UUID]
    human_explanation: str | None
    prompt_pack: PromptPackResponse
    verification_checklist: list[str]
    suggested_patch: str | None
    risks_and_tradeoffs: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class PromptTemplateResponse(BaseModel):
    id: str
    title: str
    description: str
    prompt: str
    acceptance_criteria: list[str]
    safety_constraints: list[str]
