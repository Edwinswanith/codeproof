"""Scoring service for findings.

Provides deduplication, impact scoring, exploitability scoring, and confidence scoring
to create explainable, actionable findings.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from app.analyzers.high_precision_analyzer import Finding

logger = logging.getLogger(__name__)


@dataclass
class ImpactScore:
    """Impact score for a finding."""

    score: int  # 0-100
    data_sensitivity: str  # high/medium/low
    flow_width: str  # direct/logged/third_party/internal
    regulatory_impact: list[str]  # GDPR, HIPAA, etc.
    explanation: str


@dataclass
class ExploitabilityScore:
    """Exploitability score for a finding."""

    score: int  # 0-100 (higher = more exploitable)
    authentication_required: bool
    network_exposure: str  # internet-facing/authenticated/internal
    attack_complexity: str  # direct/auth_bypass/chain
    explanation: str


@dataclass
class ConfidenceScore:
    """Confidence score for a finding."""

    score: int  # 0-100
    level: str  # high/medium/low
    reason: str
    trace_strength: str  # exact_match/structural/heuristic


@dataclass
class ScoredFinding:
    """Finding with all scores computed."""

    finding: Finding
    impact: ImpactScore
    exploitability: ExploitabilityScore
    confidence: ConfidenceScore
    dedupe_key: str


@dataclass
class FindingGroup:
    """Group of related findings (deduplicated)."""

    rule_id: str
    category: str
    findings: list[ScoredFinding]
    unique_count: int
    description: str  # Human-readable description of the issue type


class ScoringService:
    """Service for scoring and deduplicating findings."""

    # Data sensitivity mapping
    DATA_SENSITIVITY_SCORES = {
        "PII": 90,
        "credentials": 95,
        "payment_data": 90,
        "health_data": 95,
        "student_data": 85,
        "logs": 40,
        "public_data": 10,
        "configuration": 50,
    }

    # Flow width scores (higher = wider exposure)
    FLOW_WIDTH_SCORES = {
        "direct": 90,  # Direct leak (console.log, print, etc.)
        "logged": 70,  # Sent to logging service
        "third_party": 60,  # Sent to third-party service
        "internal": 30,  # Internal only
    }

    def deduplicate_findings(self, findings: list[Finding]) -> list[Finding]:
        """Deduplicate findings by rule_id + file_path + line_range + sink + source.

        Groups findings that are the same issue in nearby locations.
        Keeps the finding with highest severity/confidence from each group.
        """
        if not findings:
            return []

        # Group by dedupe key
        groups: dict[str, list[Finding]] = defaultdict(list)
        for finding in findings:
            key = self._compute_dedupe_key(finding)
            groups[key].append(finding)

        # From each group, keep the most severe/confident finding
        deduplicated = []
        for key, group_findings in groups.items():
            # Sort by severity (critical > warning > info) then by line number
            sorted_findings = sorted(
                group_findings,
                key=lambda f: (
                    f.severity.value == "critical",
                    f.severity.value == "warning",
                    f.severity.value == "info",
                    f.start_line,
                ),
                reverse=True,
            )
            deduplicated.append(sorted_findings[0])

        logger.info(f"Deduplicated {len(findings)} findings to {len(deduplicated)} unique issues")
        return deduplicated

    def _compute_dedupe_key(self, finding: Finding) -> str:
        """Compute deduplication key for a finding.

        Format: rule_id:file_path:line_range:source:sink
        """
        # Group by file and nearby lines (within 10 lines = same region)
        line_region = (finding.start_line // 10) * 10
        source = finding.evidence.source or ""
        sink = finding.evidence.sink or ""
        return f"{finding.rule_id}:{finding.file_path}:{line_region}:{source}:{sink}"

    def compute_impact_score(self, finding: Finding) -> ImpactScore:
        """Compute impact score based on data sensitivity and flow width."""
        data_types = finding.data_types or []

        # Determine data sensitivity
        max_sensitivity = 0
        sensitivity_level = "low"
        for data_type in data_types:
            score = self.DATA_SENSITIVITY_SCORES.get(data_type.lower(), 50)
            if score > max_sensitivity:
                max_sensitivity = score
                if score >= 85:
                    sensitivity_level = "high"
                elif score >= 60:
                    sensitivity_level = "medium"
                else:
                    sensitivity_level = "low"

        # Determine flow width (default to "internal" if unknown)
        flow_width = "internal"
        flow_width_score = 30

        # Check evidence for flow indicators
        rule_name_lower = finding.evidence.rule_name.lower()
        code_snippet_lower = finding.evidence.code_snippet.lower()

        if any(word in code_snippet_lower for word in ["console.log", "print(", "log(", "logger."]):
            flow_width = "logged"
            flow_width_score = 70
        elif any(word in code_snippet_lower for word in ["http", "api", "fetch", "axios", "requests."]):
            flow_width = "third_party"
            flow_width_score = 60
        elif "secret" in rule_name_lower or "key" in rule_name_lower:
            # Secrets directly in code are direct exposure
            flow_width = "direct"
            flow_width_score = 90

        # Regulatory impact
        regulatory_impact = []
        if any(dt in ["PII", "health_data", "student_data"] for dt in data_types):
            if "health" in data_types or "patient" in str(data_types).lower():
                regulatory_impact.append("HIPAA")
            if "student" in data_types or "education" in str(data_types).lower():
                regulatory_impact.append("FERPA")
            if "PII" in data_types:
                regulatory_impact.append("GDPR")
                regulatory_impact.append("CCPA")

        # Calculate overall impact score (weighted average)
        impact_score = int((max_sensitivity * 0.6 + flow_width_score * 0.4))

        # Build explanation
        explanation_parts = [f"Data sensitivity: {sensitivity_level}"]
        if data_types:
            explanation_parts.append(f"Data types: {', '.join(data_types)}")
        explanation_parts.append(f"Flow: {flow_width}")
        if regulatory_impact:
            explanation_parts.append(f"Regulatory: {', '.join(regulatory_impact)}")

        return ImpactScore(
            score=impact_score,
            data_sensitivity=sensitivity_level,
            flow_width=flow_width,
            regulatory_impact=regulatory_impact,
            explanation="; ".join(explanation_parts),
        )

    def compute_exploitability(
        self, finding: Finding, context: Optional[dict] = None
    ) -> ExploitabilityScore:
        """Compute exploitability score.

        Context can include: route_info, endpoint_info, auth_info, etc.
        """
        context = context or {}

        # Check if authentication is required (default: unknown = assume not required)
        auth_required = context.get("auth_required", False)
        network_exposure = context.get("network_exposure", "unknown")

        # Infer from file path and code
        file_path_lower = finding.file_path.lower()
        code_snippet_lower = finding.evidence.code_snippet.lower()

        # Network exposure inference
        if network_exposure == "unknown":
            if any(path in file_path_lower for path in ["routes/", "api/", "controller"]):
                network_exposure = "internet-facing"
            elif any(path in file_path_lower for path in ["internal", "private", "admin"]):
                network_exposure = "internal"
            else:
                network_exposure = "authenticated"  # Default assumption

        # Authentication inference
        if not auth_required:
            # Check code snippet for auth indicators
            if any(word in code_snippet_lower for word in ["auth", "login", "session", "token"]):
                auth_required = True
            elif "routes/" in file_path_lower and "api/" in file_path_lower:
                # API routes often require auth (but not always)
                auth_required = None  # Unknown

        # Attack complexity
        if not auth_required:
            attack_complexity = "direct"
            complexity_score = 90
        elif auth_required is None:
            attack_complexity = "auth_bypass"
            complexity_score = 60
        else:
            attack_complexity = "chain"
            complexity_score = 30

        # Network exposure scoring
        exposure_scores = {
            "internet-facing": 90,
            "authenticated": 60,
            "internal": 30,
            "unknown": 50,
        }
        exposure_score = exposure_scores.get(network_exposure, 50)

        # Overall exploitability (weighted average)
        exploitability_score = int((exposure_score * 0.6 + complexity_score * 0.4))

        # Build explanation
        explanation_parts = []
        if auth_required is not None:
            explanation_parts.append(f"Auth required: {auth_required}")
        explanation_parts.append(f"Network exposure: {network_exposure}")
        explanation_parts.append(f"Attack complexity: {attack_complexity}")

        return ExploitabilityScore(
            score=exploitability_score,
            authentication_required=auth_required if auth_required is not None else False,
            network_exposure=network_exposure,
            attack_complexity=attack_complexity,
            explanation="; ".join(explanation_parts),
        )

    def check_evidence_completeness(self, finding: Finding) -> bool:
        """Check if finding has complete evidence.
        
        Returns True if evidence is complete (file, line, snippet, reason all present).
        """
        evidence = finding.evidence
        if not evidence:
            return False
        
        # Check required fields
        if not evidence.file_path or not evidence.rule_trigger_reason:
            return False
        
        if evidence.start_line <= 0 or evidence.end_line <= 0:
            return False
        
        if not evidence.code_snippet or len(evidence.code_snippet.strip()) == 0:
            return False
        
        return True

    def auto_downgrade_speculative(self, finding: Finding) -> Finding:
        """Auto-downgrade finding severity if evidence is incomplete.
        
        If evidence is missing or incomplete, downgrades severity to INFO
        to prevent false positives.
        """
        from app.analyzers.high_precision_analyzer import Severity
        
        if not self.check_evidence_completeness(finding):
            # Downgrade to INFO
            if finding.severity != Severity.INFO:
                logger.warning(
                    f"Downgrading {finding.category.value} finding in {finding.file_path} "
                    f"from {finding.severity.value} to INFO due to incomplete evidence"
                )
                finding.severity = Severity.INFO
        return finding

    def compute_confidence(self, finding: Finding) -> ConfidenceScore:
        """Compute confidence score based on evidence quality."""
        # Confidence is determined by the type of match
        rule_name_lower = finding.evidence.rule_name.lower()
        code_snippet = finding.evidence.code_snippet

        # Check for exact pattern matches (high confidence)
        if "secret" in rule_name_lower or "key" in rule_name_lower:
            confidence_score = 95
            level = "high"
            trace_strength = "exact_match"
            reason = "Exact pattern match - high precision detection"
        elif "migration" in rule_name_lower and "drop" in rule_name_lower:
            confidence_score = 90
            level = "high"
            trace_strength = "exact_match"
            reason = "Exact structural match for destructive operation"
        elif "middleware" in rule_name_lower:
            confidence_score = 85
            level = "high"
            trace_strength = "structural"
            reason = "Structural pattern match - middleware removal detected"
        elif code_snippet and len(code_snippet) > 20:
            confidence_score = 70
            level = "medium"
            trace_strength = "structural"
            reason = "Structural match with code context"
        else:
            confidence_score = 50
            level = "low"
            trace_strength = "heuristic"
            reason = "Heuristic match - requires manual review"

        return ConfidenceScore(
            score=confidence_score,
            level=level,
            reason=reason,
            trace_strength=trace_strength,
        )

    def group_by_issue_type(self, scored_findings: list[ScoredFinding]) -> dict[str, FindingGroup]:
        """Group findings by issue type for summary reporting."""
        groups: dict[str, list[ScoredFinding]] = defaultdict(list)

        for scored in scored_findings:
            finding = scored.finding
            # Create group key from rule_id and category
            group_key = f"{finding.rule_id}:{finding.category.value}"
            groups[group_key].append(scored)

        # Convert to FindingGroup objects
        result = {}
        for group_key, findings_list in groups.items():
            first_finding = findings_list[0].finding
            rule_id = first_finding.rule_id
            category = first_finding.category.value

            # Create human-readable description
            description = self._create_group_description(first_finding, len(findings_list))

            result[group_key] = FindingGroup(
                rule_id=rule_id,
                category=category,
                findings=findings_list,
                unique_count=len(findings_list),
                description=description,
            )

        return result

    def _create_group_description(self, finding: Finding, count: int) -> str:
        """Create human-readable description for a group of findings."""
        category = finding.category.value
        rule_name = finding.evidence.rule_name

        descriptions = {
            "secret_exposure": f"{count} {rule_name} exposure(s)",
            "private_key_exposed": f"{count} private key(s) exposed",
            "env_leaked": f"{count} environment file(s) committed",
            "migration_destructive": f"{count} destructive migration(s)",
            "auth_middleware_removed": f"{count} auth middleware removal(s)",
            "dependency_changed": f"{count} dependency change(s)",
        }

        return descriptions.get(category, f"{count} {category} finding(s)")

    def score_findings(
        self, findings: list[Finding], context: Optional[dict] = None
    ) -> list[ScoredFinding]:
        """Score a list of findings.

        Returns scored findings with impact, exploitability, and confidence scores.
        Auto-downgrades findings with incomplete evidence.
        """
        scored = []
        for finding in findings:
            # Auto-downgrade speculative findings (incomplete evidence)
            finding = self.auto_downgrade_speculative(finding)
            impact = self.compute_impact_score(finding)
            exploitability = self.compute_exploitability(finding, context)
            confidence = self.compute_confidence(finding)
            dedupe_key = self._compute_dedupe_key(finding)

            scored.append(
                ScoredFinding(
                    finding=finding,
                    impact=impact,
                    exploitability=exploitability,
                    confidence=confidence,
                    dedupe_key=dedupe_key,
                )
            )

        return scored

    def create_summary_breakdown(self, groups: dict[str, FindingGroup]) -> str:
        """Create human-readable summary breakdown.

        Format: "12 unique critical flows: PII to logs (5), PII to third parties (4), missing auth on admin API (3)"
        """
        if not groups:
            return "No issues detected"

        # Sort by count (descending)
        sorted_groups = sorted(groups.values(), key=lambda g: g.unique_count, reverse=True)

        parts = []
        for group in sorted_groups:
            parts.append(f"{group.description} ({group.unique_count})")

        total = sum(g.unique_count for g in groups.values())
        summary = f"{total} unique issue(s): {', '.join(parts)}"

        return summary

