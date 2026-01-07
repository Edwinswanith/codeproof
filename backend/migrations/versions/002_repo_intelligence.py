"""Add repo intelligence scan schema.

Revision ID: 002_repo_intelligence
Revises: 001_initial_schema
Create Date: 2025-01-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "002_repo_intelligence"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        sa.Column("ref", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="queued"),
        sa.Column("config", postgresql.JSONB, server_default="{}"),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("repo_id", "commit_sha", "config_hash", name="uq_scan_runs_repo_commit_config"),
    )
    op.create_check_constraint(
        "ck_scan_runs_status",
        "scan_runs",
        "status IN ('queued', 'running', 'completed', 'failed', 'degraded')",
    )
    op.create_index("idx_scan_runs_repo", "scan_runs", ["repo_id"])

    op.create_table(
        "coverage_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_files", sa.Integer(), server_default="0"),
        sa.Column("parsed_files", sa.Integer(), server_default="0"),
        sa.Column("skipped_files", sa.Integer(), server_default="0"),
        sa.Column("skipped_reasons", postgresql.JSONB, server_default="{}"),
        sa.Column("languages", postgresql.JSONB, server_default="{}"),
        sa.Column("ast_success_rate", sa.Float(), server_default="0"),
        sa.Column("degraded_modes", postgresql.JSONB, server_default="[]"),
        sa.Column("parse_errors_count", sa.Integer(), server_default="0"),
        sa.Column("parse_errors", postgresql.JSONB, server_default="[]"),
        sa.Column("coverage_percentage", sa.Float(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("scan_run_id", name="uq_coverage_summaries_scan_run"),
    )

    op.create_table(
        "file_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.String(length=1000), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("is_binary", sa.Boolean(), server_default="false"),
        sa.Column("stored_at", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("scan_run_id", "path", name="uq_file_snapshots_scan_path"),
    )
    op.create_index("idx_file_snapshots_scan", "file_snapshots", ["scan_run_id"])

    op.create_table(
        "evidence_snippets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("file_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("file_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("snippet_text", sa.Text(), nullable=False),
        sa.Column("snippet_hash", sa.String(length=64), nullable=False),
        sa.Column("context_before_lines", sa.Text(), nullable=True),
        sa.Column("context_after_lines", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_evidence_snippets_file", "evidence_snippets", ["file_snapshot_id"])

    op.create_table(
        "trace_graphs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("nodes", postgresql.JSONB, server_default="[]"),
        sa.Column("edges", postgresql.JSONB, server_default="[]"),
        sa.Column("summary", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_check_constraint(
        "ck_trace_graphs_type",
        "trace_graphs",
        "type IN ('callgraph', 'dataflow')",
    )
    op.create_index("idx_trace_graphs_scan", "trace_graphs", ["scan_run_id"])

    op.create_table(
        "fix_packs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("scope", sa.String(length=30), nullable=False),
        sa.Column("finding_ids", postgresql.JSONB, server_default="[]"),
        sa.Column("human_explanation", sa.Text(), nullable=True),
        sa.Column("prompt_pack", postgresql.JSONB, server_default="{}"),
        sa.Column("verification_checklist", postgresql.JSONB, server_default="[]"),
        sa.Column("suggested_patch", sa.Text(), nullable=True),
        sa.Column("risks_and_tradeoffs", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_check_constraint(
        "ck_fix_packs_scope",
        "fix_packs",
        "scope IN ('single_finding', 'multi_finding', 'module', 'pr')",
    )
    op.create_index("idx_fix_packs_scan", "fix_packs", ["scan_run_id"])

    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("confidence_rationale", postgresql.JSONB, server_default="{}"),
        sa.Column("impact", postgresql.JSONB, server_default="{}"),
        sa.Column("likelihood", postgresql.JSONB, server_default="{}"),
        sa.Column("remediation_summary", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB, server_default="[]"),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("scan_run_id", "dedupe_key", name="uq_findings_scan_dedupe"),
    )
    op.create_check_constraint(
        "ck_findings_category",
        "findings",
        "category IN ('security', 'privacy', 'compliance', 'reliability', 'performance', 'maintainability', 'architecture')",
    )
    op.create_check_constraint(
        "ck_findings_severity",
        "findings",
        "severity IN ('critical', 'high', 'medium', 'low', 'info')",
    )
    op.create_check_constraint(
        "ck_findings_confidence",
        "findings",
        "confidence IN ('high', 'medium', 'low', 'unknown')",
    )
    op.create_index("idx_findings_scan", "findings", ["scan_run_id"])
    op.create_index("idx_findings_category", "findings", ["scan_run_id", "category"])
    op.create_index("idx_findings_severity", "findings", ["scan_run_id", "severity"])

    op.create_table(
        "finding_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_snippet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence_snippets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("symbols.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_to_sink_trace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trace_graphs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("retrieval_score", sa.Float(), nullable=True),
        sa.Column("instance_severity_override", sa.String(length=20), nullable=True),
        sa.Column("instance_confidence_override", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_finding_instances_finding", "finding_instances", ["finding_id"])

    op.create_table(
        "control_frameworks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("region", sa.String(length=50), nullable=False),
        sa.Column("sector", sa.String(length=50), nullable=True),
        sa.Column("version", sa.String(length=20), nullable=True),
        sa.Column("controls", postgresql.JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_control_frameworks_region", "control_frameworks", ["region"])

    op.create_table(
        "control_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_framework_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("control_frameworks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("evidence_instance_ids", postgresql.JSONB, server_default="[]"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("fix_pack_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fix_packs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_check_constraint(
        "ck_control_results_status",
        "control_results",
        "status IN ('pass', 'fail', 'unknown')",
    )
    op.create_index("idx_control_results_scan", "control_results", ["scan_run_id"])


def downgrade() -> None:
    op.drop_table("control_results")
    op.drop_table("control_frameworks")
    op.drop_table("finding_instances")
    op.drop_table("findings")
    op.drop_table("fix_packs")
    op.drop_table("trace_graphs")
    op.drop_table("evidence_snippets")
    op.drop_table("file_snapshots")
    op.drop_table("coverage_summaries")
    op.drop_table("scan_runs")
