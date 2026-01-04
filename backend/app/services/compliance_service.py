"""Compliance Analysis Service.

Analyzes code repositories for regulatory compliance based on:
- Target deployment country/region
- Industry sector
- Applicable regulations (GDPR, HIPAA, PCI-DSS, SOC2, etc.)

Uses Gemini AI to research requirements and analyze code.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Region(str, Enum):
    """Supported deployment regions."""
    EU = "eu"
    US = "us"
    UK = "uk"
    INDIA = "india"
    AUSTRALIA = "australia"
    CANADA = "canada"
    BRAZIL = "brazil"
    SINGAPORE = "singapore"
    UAE = "uae"
    GLOBAL = "global"


class IndustrySector(str, Enum):
    """Industry sectors with specific compliance requirements."""
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    ECOMMERCE = "ecommerce"
    EDUCATION = "education"
    GOVERNMENT = "government"
    SAAS = "saas"
    SOCIAL_MEDIA = "social_media"
    IOT = "iot"
    AI_ML = "ai_ml"
    GENERAL = "general"


@dataclass
class Regulation:
    """A regulatory framework."""
    code: str
    name: str
    description: str
    regions: list[str]
    sectors: list[str]
    key_requirements: list[str]
    penalties: str
    official_url: str


@dataclass
class ComplianceCheck:
    """A specific compliance check to perform."""
    id: str
    regulation: str
    category: str
    name: str
    description: str
    severity: str  # critical, high, medium, low
    patterns: list[str]  # Code patterns to look for
    required_patterns: list[str]  # Patterns that MUST exist
    forbidden_patterns: list[str]  # Patterns that MUST NOT exist
    recommendations: list[str]


@dataclass
class ComplianceFinding:
    """A compliance issue found in code."""
    check_id: str
    regulation: str
    category: str
    severity: str
    title: str
    description: str
    file_path: str
    line_start: int
    line_end: int
    code_snippet: str
    recommendation: str
    reference_url: str


@dataclass
class ComplianceReport:
    """Complete compliance analysis report."""
    region: str
    sector: str
    applicable_regulations: list[Regulation]
    findings: list[ComplianceFinding]
    summary: dict
    ai_analysis: str
    recommendations: list[str]
    compliance_score: float  # 0-100
    risk_level: str  # critical, high, medium, low


# Define major regulations
REGULATIONS: dict[str, Regulation] = {
    "GDPR": Regulation(
        code="GDPR",
        name="General Data Protection Regulation",
        description="EU regulation on data protection and privacy",
        regions=["eu", "uk", "global"],
        sectors=["all"],
        key_requirements=[
            "Lawful basis for processing personal data",
            "Data subject rights (access, erasure, portability)",
            "Data protection by design and default",
            "Data breach notification within 72 hours",
            "Data Protection Impact Assessments",
            "Consent management",
            "Right to be forgotten",
            "Data minimization",
        ],
        penalties="Up to €20 million or 4% of global annual turnover",
        official_url="https://gdpr.eu/",
    ),
    "CCPA": Regulation(
        code="CCPA",
        name="California Consumer Privacy Act",
        description="California state privacy law",
        regions=["us"],
        sectors=["all"],
        key_requirements=[
            "Right to know what data is collected",
            "Right to delete personal information",
            "Right to opt-out of data sale",
            "Non-discrimination for exercising rights",
            "Privacy policy disclosure",
        ],
        penalties="$2,500-$7,500 per violation",
        official_url="https://oag.ca.gov/privacy/ccpa",
    ),
    "HIPAA": Regulation(
        code="HIPAA",
        name="Health Insurance Portability and Accountability Act",
        description="US healthcare data protection law",
        regions=["us"],
        sectors=["healthcare"],
        key_requirements=[
            "Protected Health Information (PHI) safeguards",
            "Access controls and audit trails",
            "Encryption of data at rest and in transit",
            "Business Associate Agreements",
            "Minimum necessary standard",
            "Breach notification",
        ],
        penalties="$100-$50,000 per violation, up to $1.5M annually",
        official_url="https://www.hhs.gov/hipaa/",
    ),
    "PCI_DSS": Regulation(
        code="PCI_DSS",
        name="Payment Card Industry Data Security Standard",
        description="Payment card data security requirements",
        regions=["global"],
        sectors=["finance", "ecommerce"],
        key_requirements=[
            "Secure network and systems",
            "Protect cardholder data",
            "Vulnerability management",
            "Strong access control",
            "Regular monitoring and testing",
            "Information security policy",
            "No storage of sensitive authentication data",
        ],
        penalties="$5,000-$100,000 per month until compliant",
        official_url="https://www.pcisecuritystandards.org/",
    ),
    "SOC2": Regulation(
        code="SOC2",
        name="Service Organization Control 2",
        description="Trust service criteria for service providers",
        regions=["global"],
        sectors=["saas", "finance"],
        key_requirements=[
            "Security controls",
            "Availability controls",
            "Processing integrity",
            "Confidentiality",
            "Privacy",
            "Access management",
            "Change management",
            "Risk assessment",
        ],
        penalties="Loss of certification, customer trust",
        official_url="https://www.aicpa.org/soc",
    ),
    "DPDP": Regulation(
        code="DPDP",
        name="Digital Personal Data Protection Act",
        description="India's data protection law",
        regions=["india"],
        sectors=["all"],
        key_requirements=[
            "Consent for data processing",
            "Purpose limitation",
            "Data localization requirements",
            "Data fiduciary obligations",
            "Rights of data principals",
            "Grievance redressal",
        ],
        penalties="Up to ₹250 crore (~$30M USD)",
        official_url="https://www.meity.gov.in/",
    ),
    "LGPD": Regulation(
        code="LGPD",
        name="Lei Geral de Proteção de Dados",
        description="Brazil's general data protection law",
        regions=["brazil"],
        sectors=["all"],
        key_requirements=[
            "Legal basis for processing",
            "Data subject rights",
            "Data Protection Officer",
            "Security measures",
            "Breach notification",
            "International data transfers",
        ],
        penalties="Up to 2% of revenue, max R$50 million per violation",
        official_url="https://www.gov.br/cidadania/pt-br/acesso-a-informacao/lgpd",
    ),
    "PDPA_SG": Regulation(
        code="PDPA_SG",
        name="Personal Data Protection Act (Singapore)",
        description="Singapore's data protection law",
        regions=["singapore"],
        sectors=["all"],
        key_requirements=[
            "Consent obligation",
            "Purpose limitation",
            "Notification obligation",
            "Access and correction rights",
            "Accuracy obligation",
            "Protection obligation",
            "Retention limitation",
            "Transfer limitation",
        ],
        penalties="Up to S$1 million",
        official_url="https://www.pdpc.gov.sg/",
    ),
}

# Compliance checks by category
COMPLIANCE_CHECKS: list[ComplianceCheck] = [
    # Data Privacy Checks
    ComplianceCheck(
        id="DP001",
        regulation="GDPR,CCPA,DPDP,LGPD",
        category="Data Privacy",
        name="Personal Data Collection Without Consent",
        description="Collecting personal data without explicit consent mechanism",
        severity="critical",
        patterns=[
            r"email|phone|address|name|ssn|passport|dob|birth",
            r"user\.email|user\.phone|user\.address",
            r"personal_data|pii|sensitive_data",
        ],
        required_patterns=[
            r"consent|gdpr_consent|privacy_consent|opt_in",
            r"accept.*terms|agree.*privacy",
        ],
        forbidden_patterns=[],
        recommendations=[
            "Implement explicit consent collection before gathering personal data",
            "Add consent checkboxes with clear privacy policy links",
            "Store consent records with timestamps",
        ],
    ),
    ComplianceCheck(
        id="DP002",
        regulation="GDPR",
        category="Data Privacy",
        name="Missing Right to Erasure Implementation",
        description="No mechanism to delete user data on request",
        severity="high",
        patterns=[r"delete.*user|remove.*account|gdpr.*delete"],
        required_patterns=[
            r"delete_user_data|erase_personal|forget_me|right_to_erasure",
            r"cascade.*delete|purge.*user",
        ],
        forbidden_patterns=[],
        recommendations=[
            "Implement user data deletion endpoint",
            "Ensure cascading deletes for all related data",
            "Add data export functionality for portability",
        ],
    ),
    ComplianceCheck(
        id="DP003",
        regulation="GDPR,CCPA",
        category="Data Privacy",
        name="Missing Data Export/Portability",
        description="No mechanism for users to export their data",
        severity="medium",
        patterns=[],
        required_patterns=[
            r"export.*data|download.*data|data_portability",
            r"user.*export|gdpr.*export",
        ],
        forbidden_patterns=[],
        recommendations=[
            "Implement data export endpoint returning JSON/CSV",
            "Include all personal data in export",
            "Document data format for interoperability",
        ],
    ),
    # Security Checks
    ComplianceCheck(
        id="SEC001",
        regulation="PCI_DSS,HIPAA,SOC2",
        category="Security",
        name="Plaintext Password Storage",
        description="Storing passwords without proper hashing",
        severity="critical",
        patterns=[
            r"password\s*=|pwd\s*=",
            r"INSERT.*password|UPDATE.*password",
        ],
        required_patterns=[],
        forbidden_patterns=[
            r"password\s*=\s*['\"]|md5\(.*password|sha1\(.*password",
            r"base64.*password|encode.*password",
        ],
        recommendations=[
            "Use bcrypt, Argon2, or PBKDF2 for password hashing",
            "Never store plaintext or weakly hashed passwords",
            "Implement password strength requirements",
        ],
    ),
    ComplianceCheck(
        id="SEC002",
        regulation="PCI_DSS,HIPAA,SOC2",
        category="Security",
        name="Missing Encryption for Sensitive Data",
        description="Sensitive data stored or transmitted without encryption",
        severity="critical",
        patterns=[
            r"credit_card|card_number|cvv|ssn|social_security",
            r"health_record|medical|diagnosis|patient",
        ],
        required_patterns=[
            r"encrypt|aes|cipher|crypto|fernet",
            r"https|tls|ssl",
        ],
        forbidden_patterns=[
            r"http://(?!localhost|127\.0\.0\.1)",
        ],
        recommendations=[
            "Encrypt all sensitive data at rest using AES-256",
            "Use TLS 1.2+ for all data in transit",
            "Implement key rotation policies",
        ],
    ),
    ComplianceCheck(
        id="SEC003",
        regulation="PCI_DSS",
        category="Security",
        name="Credit Card Data Storage",
        description="Storing full credit card numbers or CVV",
        severity="critical",
        patterns=[],
        required_patterns=[],
        forbidden_patterns=[
            r"cvv|cvc|security_code|card_verification",
            r"full_card|card_number(?!_last4|_token)",
            r"pan\s*=|primary_account_number",
        ],
        recommendations=[
            "Never store CVV/CVC codes",
            "Use payment tokenization (Stripe, Braintree)",
            "Only store last 4 digits for reference",
        ],
    ),
    ComplianceCheck(
        id="SEC004",
        regulation="HIPAA,SOC2",
        category="Security",
        name="Missing Audit Logging",
        description="No audit trail for data access and modifications",
        severity="high",
        patterns=[],
        required_patterns=[
            r"audit.*log|access.*log|activity.*log",
            r"logger\.info.*access|log.*action",
            r"created_by|modified_by|accessed_at",
        ],
        forbidden_patterns=[],
        recommendations=[
            "Implement comprehensive audit logging",
            "Log all data access, modifications, and deletions",
            "Include user ID, timestamp, action, and affected records",
            "Store logs securely for required retention period",
        ],
    ),
    ComplianceCheck(
        id="SEC005",
        regulation="HIPAA,PCI_DSS,SOC2",
        category="Security",
        name="Insufficient Access Controls",
        description="Missing role-based access control or authorization checks",
        severity="high",
        patterns=[
            r"admin|superuser|root|privileged",
        ],
        required_patterns=[
            r"@requires_auth|@login_required|@authenticated",
            r"check_permission|has_permission|authorize",
            r"role.*check|rbac|acl",
        ],
        forbidden_patterns=[],
        recommendations=[
            "Implement role-based access control (RBAC)",
            "Add authorization checks to all sensitive endpoints",
            "Follow principle of least privilege",
        ],
    ),
    # Data Retention
    ComplianceCheck(
        id="RET001",
        regulation="GDPR,CCPA,DPDP",
        category="Data Retention",
        name="Missing Data Retention Policy",
        description="No automated data cleanup or retention limits",
        severity="medium",
        patterns=[],
        required_patterns=[
            r"retention|expire|cleanup|purge|ttl",
            r"delete.*old|remove.*expired",
            r"data_retention|retention_policy",
        ],
        forbidden_patterns=[],
        recommendations=[
            "Define data retention periods for each data type",
            "Implement automated data cleanup jobs",
            "Document retention policy in privacy policy",
        ],
    ),
    # International Data Transfer
    ComplianceCheck(
        id="INT001",
        regulation="GDPR,DPDP",
        category="International Transfer",
        name="Cross-Border Data Transfer Without Safeguards",
        description="Transferring personal data internationally without proper mechanisms",
        severity="high",
        patterns=[
            r"aws|azure|gcp|cloud",
            r"cdn|cloudflare|fastly",
            r"analytics|tracking|third.*party",
        ],
        required_patterns=[
            r"data_processing_agreement|dpa|scc|standard_contractual",
            r"adequacy|privacy_shield|binding_corporate",
        ],
        forbidden_patterns=[],
        recommendations=[
            "Document all international data transfers",
            "Implement Standard Contractual Clauses (SCCs)",
            "Conduct Transfer Impact Assessments",
            "Consider data localization where required",
        ],
    ),
    # Breach Notification
    ComplianceCheck(
        id="BRE001",
        regulation="GDPR,HIPAA,CCPA",
        category="Breach Response",
        name="Missing Breach Notification Mechanism",
        description="No system for detecting and reporting data breaches",
        severity="high",
        patterns=[],
        required_patterns=[
            r"breach|incident|security_event",
            r"notify.*breach|alert.*security|incident_response",
        ],
        forbidden_patterns=[],
        recommendations=[
            "Implement security monitoring and alerting",
            "Create incident response procedures",
            "Build breach notification system (72 hours for GDPR)",
            "Document breach response plan",
        ],
    ),
    # Healthcare Specific
    ComplianceCheck(
        id="HIP001",
        regulation="HIPAA",
        category="Healthcare",
        name="PHI Without BAA",
        description="Processing health information without Business Associate Agreement",
        severity="critical",
        patterns=[
            r"patient|medical|health|diagnosis|treatment",
            r"prescription|medication|lab_result",
            r"phi|protected_health|hipaa",
        ],
        required_patterns=[
            r"baa|business_associate|covered_entity",
        ],
        forbidden_patterns=[],
        recommendations=[
            "Ensure BAAs with all vendors processing PHI",
            "Document all PHI data flows",
            "Implement minimum necessary standard",
        ],
    ),
    # AI/ML Specific
    ComplianceCheck(
        id="AI001",
        regulation="GDPR,EU_AI_ACT",
        category="AI/ML",
        name="Automated Decision Making Without Disclosure",
        description="Using AI for decisions affecting users without transparency",
        severity="high",
        patterns=[
            r"predict|classify|recommend|score",
            r"model\.predict|inference|ml_decision",
            r"automated.*decision|algorithm.*decide",
        ],
        required_patterns=[
            r"explain|interpretab|transparen|ai_disclosure",
            r"human.*review|manual.*override|appeal",
        ],
        forbidden_patterns=[],
        recommendations=[
            "Disclose use of automated decision-making",
            "Provide explanation of AI decisions",
            "Implement human review for significant decisions",
            "Allow users to contest automated decisions",
        ],
    ),
]


class ComplianceService:
    """Service for analyzing code compliance with regulations."""

    def __init__(self):
        """Initialize compliance service."""
        self.client = None
        self._init_gemini()

    def _init_gemini(self):
        """Initialize Gemini client."""
        try:
            from google import genai
            if settings.gemini_api_key:
                self.client = genai.Client(api_key=settings.gemini_api_key)
                logger.info("Initialized Gemini client for compliance analysis")
            else:
                logger.warning("GEMINI_API_KEY not set, AI analysis disabled")
        except ImportError:
            logger.warning("google-genai not installed")

    def get_applicable_regulations(
        self,
        region: str,
        sector: str
    ) -> list[Regulation]:
        """Get regulations applicable to given region and sector."""
        applicable = []

        for reg in REGULATIONS.values():
            # Check region match
            region_match = (
                region in reg.regions or
                "global" in reg.regions or
                region == "global"
            )

            # Check sector match
            sector_match = (
                sector in reg.sectors or
                "all" in reg.sectors
            )

            if region_match and sector_match:
                applicable.append(reg)

        return applicable

    def get_applicable_checks(
        self,
        regulations: list[Regulation]
    ) -> list[ComplianceCheck]:
        """Get compliance checks for given regulations."""
        reg_codes = {r.code for r in regulations}
        applicable_checks = []

        for check in COMPLIANCE_CHECKS:
            check_regs = set(check.regulation.split(","))
            if check_regs & reg_codes:
                applicable_checks.append(check)

        return applicable_checks

    async def analyze_compliance(
        self,
        code_files: dict[str, str],  # file_path -> content
        region: str,
        sector: str,
        symbols: list = None,
    ) -> ComplianceReport:
        """
        Analyze code for compliance issues.

        Args:
            code_files: Dictionary mapping file paths to their content
            region: Target deployment region
            sector: Industry sector
            symbols: Optional parsed symbols for deeper analysis

        Returns:
            ComplianceReport with findings and recommendations
        """
        import re

        # Get applicable regulations and checks
        regulations = self.get_applicable_regulations(region, sector)
        checks = self.get_applicable_checks(regulations)

        findings: list[ComplianceFinding] = []

        # Run each check against the codebase
        for check in checks:
            check_findings = self._run_check(check, code_files)
            findings.extend(check_findings)

        # Calculate compliance score
        critical_count = sum(1 for f in findings if f.severity == "critical")
        high_count = sum(1 for f in findings if f.severity == "high")
        medium_count = sum(1 for f in findings if f.severity == "medium")
        low_count = sum(1 for f in findings if f.severity == "low")

        # Score calculation (penalize more for critical issues)
        total_penalty = (critical_count * 25) + (high_count * 10) + (medium_count * 5) + (low_count * 2)
        compliance_score = max(0, 100 - total_penalty)

        # Determine risk level
        if critical_count > 0:
            risk_level = "critical"
        elif high_count > 2:
            risk_level = "high"
        elif high_count > 0 or medium_count > 3:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Generate AI analysis if available
        ai_analysis = ""
        recommendations = []

        if self.client and findings:
            ai_analysis, recommendations = await self._generate_ai_analysis(
                region, sector, regulations, findings, code_files
            )
        else:
            # Generate basic recommendations from findings
            seen_recs = set()
            for finding in findings:
                if finding.recommendation not in seen_recs:
                    recommendations.append(finding.recommendation)
                    seen_recs.add(finding.recommendation)

        # Build summary
        summary = {
            "total_findings": len(findings),
            "critical": critical_count,
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
            "regulations_checked": len(regulations),
            "checks_performed": len(checks),
            "files_analyzed": len(code_files),
        }

        return ComplianceReport(
            region=region,
            sector=sector,
            applicable_regulations=regulations,
            findings=findings,
            summary=summary,
            ai_analysis=ai_analysis,
            recommendations=recommendations[:10],  # Top 10 recommendations
            compliance_score=compliance_score,
            risk_level=risk_level,
        )

    def _run_check(
        self,
        check: ComplianceCheck,
        code_files: dict[str, str]
    ) -> list[ComplianceFinding]:
        """Run a single compliance check against all code files."""
        import re

        findings = []

        for file_path, content in code_files.items():
            # Skip non-code files
            if not self._is_code_file(file_path):
                continue

            lines = content.split('\n')

            # Check for forbidden patterns
            for pattern in check.forbidden_patterns:
                try:
                    for i, line in enumerate(lines):
                        if re.search(pattern, line, re.IGNORECASE):
                            findings.append(ComplianceFinding(
                                check_id=check.id,
                                regulation=check.regulation,
                                category=check.category,
                                severity=check.severity,
                                title=check.name,
                                description=check.description,
                                file_path=file_path,
                                line_start=i + 1,
                                line_end=i + 1,
                                code_snippet=self._get_snippet(lines, i),
                                recommendation=check.recommendations[0] if check.recommendations else "",
                                reference_url=self._get_regulation_url(check.regulation),
                            ))
                except re.error:
                    logger.warning(f"Invalid regex pattern: {pattern}")

            # Check for required patterns (if patterns exist but required ones don't)
            if check.patterns and check.required_patterns:
                has_pattern = any(
                    re.search(p, content, re.IGNORECASE)
                    for p in check.patterns
                )
                has_required = any(
                    re.search(p, content, re.IGNORECASE)
                    for p in check.required_patterns
                )

                if has_pattern and not has_required:
                    # Find where the pattern occurs
                    for pattern in check.patterns:
                        try:
                            for i, line in enumerate(lines):
                                if re.search(pattern, line, re.IGNORECASE):
                                    findings.append(ComplianceFinding(
                                        check_id=check.id,
                                        regulation=check.regulation,
                                        category=check.category,
                                        severity=check.severity,
                                        title=check.name,
                                        description=f"{check.description}. Missing required implementation.",
                                        file_path=file_path,
                                        line_start=i + 1,
                                        line_end=i + 1,
                                        code_snippet=self._get_snippet(lines, i),
                                        recommendation=check.recommendations[0] if check.recommendations else "",
                                        reference_url=self._get_regulation_url(check.regulation),
                                    ))
                                    break  # One finding per file per check
                        except re.error:
                            pass

        return findings

    def _is_code_file(self, path: str) -> bool:
        """Check if file is a code file worth analyzing."""
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.php', '.rb', '.java',
            '.go', '.rs', '.cs', '.vue', '.svelte', '.blade.php'
        }
        return any(path.endswith(ext) for ext in code_extensions)

    def _get_snippet(self, lines: list[str], line_idx: int, context: int = 2) -> str:
        """Get code snippet with context."""
        start = max(0, line_idx - context)
        end = min(len(lines), line_idx + context + 1)
        snippet_lines = []
        for i in range(start, end):
            prefix = ">>> " if i == line_idx else "    "
            snippet_lines.append(f"{i+1:4d} {prefix}{lines[i]}")
        return '\n'.join(snippet_lines)

    def _get_regulation_url(self, regulation_codes: str) -> str:
        """Get official URL for first regulation in list."""
        first_code = regulation_codes.split(",")[0]
        if first_code in REGULATIONS:
            return REGULATIONS[first_code].official_url
        return ""

    async def _generate_ai_analysis(
        self,
        region: str,
        sector: str,
        regulations: list[Regulation],
        findings: list[ComplianceFinding],
        code_files: dict[str, str],
    ) -> tuple[str, list[str]]:
        """Generate AI-powered analysis and recommendations."""

        # Build context
        reg_names = ", ".join(r.name for r in regulations)
        finding_summary = []
        for f in findings[:20]:  # Limit to first 20
            finding_summary.append(
                f"- [{f.severity.upper()}] {f.title} in {f.file_path}:{f.line_start}"
            )

        prompt = f"""You are a compliance expert analyzing a software codebase for regulatory compliance.

DEPLOYMENT CONTEXT:
- Region: {region.upper()}
- Industry Sector: {sector}
- Applicable Regulations: {reg_names}

FINDINGS DETECTED:
{chr(10).join(finding_summary) if finding_summary else "No automated findings detected."}

TASK:
1. Provide a brief executive summary of the compliance status (2-3 sentences)
2. Identify the TOP 5 most critical compliance gaps based on the findings
3. For each gap, provide a specific, actionable recommendation
4. Consider industry best practices for {sector} in {region.upper()}

Be specific and practical. Focus on the highest-risk items first.
Format recommendations as a numbered list.

OUTPUT FORMAT:
## Executive Summary
[2-3 sentence summary]

## Critical Gaps & Recommendations
1. [Gap]: [Specific recommendation]
2. [Gap]: [Specific recommendation]
...
"""

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=settings.gemini_model,
                contents=prompt,
            )

            analysis_text = response.text

            # Extract recommendations
            recommendations = []
            import re
            rec_pattern = r'\d+\.\s+(?:\[.*?\]:\s*)?(.+?)(?=\n\d+\.|\n##|$)'
            matches = re.findall(rec_pattern, analysis_text, re.DOTALL)
            for match in matches:
                rec = match.strip()
                if rec and len(rec) > 10:
                    recommendations.append(rec)

            return analysis_text, recommendations

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return "", []

    async def research_regulations(
        self,
        region: str,
        sector: str,
    ) -> dict:
        """Use AI to research current regulations for region/sector."""

        if not self.client:
            return {
                "regulations": self.get_applicable_regulations(region, sector),
                "research": "AI research unavailable - using predefined regulations",
            }

        prompt = f"""You are a regulatory compliance expert. Research the current data protection and security regulations for:

REGION: {region.upper()}
INDUSTRY: {sector}

Provide:
1. List of applicable regulations with:
   - Full name
   - Key requirements (3-5 bullet points)
   - Penalties for non-compliance
   - Effective date or recent updates (if any in 2024-2025)

2. Industry-specific requirements for {sector}

3. Any upcoming regulations to be aware of

Be accurate and cite specific laws/acts. Focus on data privacy, security, and sector-specific requirements.
"""

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=settings.gemini_model,
                contents=prompt,
            )

            return {
                "regulations": self.get_applicable_regulations(region, sector),
                "research": response.text,
            }

        except Exception as e:
            logger.error(f"Regulation research failed: {e}")
            return {
                "regulations": self.get_applicable_regulations(region, sector),
                "research": f"Research failed: {str(e)}",
            }
