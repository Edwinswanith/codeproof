"""Scan and repo intelligence models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.repository import Repository


class ScanRun(Base):
    """Scan run for a repository commit."""

    __tablename__ = "scan_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    ref: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    repo: Mapped["Repository"] = relationship("Repository")
    coverage_summary: Mapped["CoverageSummary"] = relationship(
        "CoverageSummary",
        back_populates="scan_run",
        uselist=False,
        cascade="all, delete-orphan",
    )
    findings: Mapped[list["Finding"]] = relationship(
        "Finding",
        back_populates="scan_run",
        cascade="all, delete-orphan",
    )
    file_snapshots: Mapped[list["FileSnapshot"]] = relationship(
        "FileSnapshot",
        back_populates="scan_run",
        cascade="all, delete-orphan",
    )
    trace_graphs: Mapped[list["TraceGraph"]] = relationship(
        "TraceGraph",
        back_populates="scan_run",
        cascade="all, delete-orphan",
    )
    control_results: Mapped[list["ControlResult"]] = relationship(
        "ControlResult",
        back_populates="scan_run",
        cascade="all, delete-orphan",
    )
    fix_packs: Mapped[list["FixPack"]] = relationship(
        "FixPack",
        back_populates="scan_run",
        cascade="all, delete-orphan",
    )


class CoverageSummary(Base):
    """Coverage summary for a scan run."""

    __tablename__ = "coverage_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False
    )
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    parsed_files: Mapped[int] = mapped_column(Integer, default=0)
    skipped_files: Mapped[int] = mapped_column(Integer, default=0)
    skipped_reasons: Mapped[dict] = mapped_column(JSONB, default=dict)
    languages: Mapped[dict] = mapped_column(JSONB, default=dict)
    ast_success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    degraded_modes: Mapped[list] = mapped_column(JSONB, default=list)
    parse_errors_count: Mapped[int] = mapped_column(Integer, default=0)
    parse_errors: Mapped[list] = mapped_column(JSONB, default=list)
    coverage_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    scan_run: Mapped["ScanRun"] = relationship("ScanRun", back_populates="coverage_summary")


class FileSnapshot(Base):
    """File snapshot captured during a scan."""

    __tablename__ = "file_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    language: Mapped[str | None] = mapped_column(String(50))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    is_binary: Mapped[bool] = mapped_column(Boolean, default=False)
    stored_at: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    scan_run: Mapped["ScanRun"] = relationship("ScanRun", back_populates="file_snapshots")
    evidence_snippets: Mapped[list["EvidenceSnippet"]] = relationship(
        "EvidenceSnippet",
        back_populates="file_snapshot",
        cascade="all, delete-orphan",
    )


class EvidenceSnippet(Base):
    """Evidence snippet captured from a file snapshot."""

    __tablename__ = "evidence_snippets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    file_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("file_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet_text: Mapped[str] = mapped_column(Text, nullable=False)
    snippet_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context_before_lines: Mapped[str | None] = mapped_column(Text)
    context_after_lines: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    file_snapshot: Mapped["FileSnapshot"] = relationship("FileSnapshot", back_populates="evidence_snippets")
    finding_instances: Mapped[list["FindingInstance"]] = relationship(
        "FindingInstance",
        back_populates="evidence_snippet",
        cascade="all, delete-orphan",
    )


class Finding(Base):
    """Root finding (deduped)."""

    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_rationale: Mapped[dict] = mapped_column(JSONB, default=dict)
    impact: Mapped[dict] = mapped_column(JSONB, default=dict)
    likelihood: Mapped[dict] = mapped_column(JSONB, default=dict)
    remediation_summary: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    scan_run: Mapped["ScanRun"] = relationship("ScanRun", back_populates="findings")
    instances: Mapped[list["FindingInstance"]] = relationship(
        "FindingInstance",
        back_populates="finding",
        cascade="all, delete-orphan",
    )


class FindingInstance(Base):
    """Evidence occurrence for a finding."""

    __tablename__ = "finding_instances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    evidence_snippet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_snippets.id", ondelete="CASCADE"), nullable=False
    )
    symbol_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("symbols.id", ondelete="SET NULL")
    )
    source_to_sink_trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trace_graphs.id", ondelete="SET NULL")
    )
    retrieval_score: Mapped[float | None] = mapped_column(Float)
    instance_severity_override: Mapped[str | None] = mapped_column(String(20))
    instance_confidence_override: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    finding: Mapped["Finding"] = relationship("Finding", back_populates="instances")
    evidence_snippet: Mapped["EvidenceSnippet"] = relationship(
        "EvidenceSnippet", back_populates="finding_instances"
    )
    trace_graph: Mapped["TraceGraph"] = relationship("TraceGraph")


class TraceGraph(Base):
    """Callgraph or dataflow graph stored for a scan."""

    __tablename__ = "trace_graphs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    nodes: Mapped[list] = mapped_column(JSONB, default=list)
    edges: Mapped[list] = mapped_column(JSONB, default=list)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    scan_run: Mapped["ScanRun"] = relationship("ScanRun", back_populates="trace_graphs")


class ControlFramework(Base):
    """Compliance control framework (GDPR, CCPA, etc.)."""

    __tablename__ = "control_frameworks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(50))
    version: Mapped[str | None] = mapped_column(String(20))
    controls: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ControlResult(Base):
    """Control evaluation results for a scan."""

    __tablename__ = "control_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False
    )
    control_framework_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("control_frameworks.id", ondelete="CASCADE"), nullable=False
    )
    control_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_instance_ids: Mapped[list] = mapped_column(JSONB, default=list)
    rationale: Mapped[str | None] = mapped_column(Text)
    fix_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fix_packs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    scan_run: Mapped["ScanRun"] = relationship("ScanRun", back_populates="control_results")
    control_framework: Mapped["ControlFramework"] = relationship("ControlFramework")
    fix_pack: Mapped["FixPack"] = relationship("FixPack")


class FixPack(Base):
    """Fix pack for findings."""

    __tablename__ = "fix_packs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[str | None] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(30), nullable=False)
    finding_ids: Mapped[list] = mapped_column(JSONB, default=list)
    human_explanation: Mapped[str | None] = mapped_column(Text)
    prompt_pack: Mapped[dict] = mapped_column(JSONB, default=dict)
    verification_checklist: Mapped[list] = mapped_column(JSONB, default=list)
    suggested_patch: Mapped[str | None] = mapped_column(Text)
    risks_and_tradeoffs: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    scan_run: Mapped["ScanRun"] = relationship("ScanRun", back_populates="fix_packs")
