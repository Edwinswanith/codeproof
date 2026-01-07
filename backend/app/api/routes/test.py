"""Test routes for direct GitHub repo analysis without OAuth.

DESIGN PRINCIPLE: Deterministic detection only. LLM never detects.
- High-precision analyzer finds SPECIFIC issues with EXACT evidence
- Every finding has: file, line, code snippet, reason, confidence
- Empty results are valid: "No high-risk issues detected"
- No generic recommendations, no made-up scores
"""

import asyncio
import httpx
import logging
import re
from typing import Optional
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.services.llm_service import LLMService

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter()


def get_github_headers() -> dict:
    """Get GitHub API headers with authentication if available."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


class RepoAnalyzeRequest(BaseModel):
    """Request to analyze a GitHub repo."""
    repo_url: str
    branch: Optional[str] = None


class EvidenceInfo(BaseModel):
    """Structured evidence for a finding."""
    file_path: str
    start_line: int
    end_line: int
    code_snippet: str
    rule_name: str
    rule_trigger_reason: str
    pattern_matched: Optional[str] = None
    context_lines: Optional[str] = None


class Finding(BaseModel):
    """A specific, evidence-based finding with structured evidence."""
    severity: str  # critical, warning, info
    category: str
    file_path: str
    line_number: int
    code_snippet: str  # Actual code from the file
    reason: str  # Specific reason, not generic
    confidence: str  # high/medium/low (from confidence scoring)
    suggested_fix: Optional[str] = None
    rule_id: Optional[str] = None  # Rule that triggered this finding
    data_types: Optional[list[str]] = None  # Data types involved
    evidence: Optional[EvidenceInfo] = None  # Structured evidence


class RepoAnalyzeResponse(BaseModel):
    """Response from repo analysis."""
    repo: str
    branch: str
    files_analyzed: int
    summary: str  # Human-readable summary
    findings: list[Finding]
    # No scores - just counts
    critical_count: int
    warning_count: int
    info_count: int


class AskRepoRequest(BaseModel):
    """Request to ask a question about a repo."""
    repo_url: str
    question: str
    file_paths: Optional[list[str]] = None


class AskRepoResponse(BaseModel):
    """Response from asking about a repo."""
    answer: str
    sources: list[dict]


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse GitHub URL to extract owner and repo name."""
    patterns = [
        r"github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/.*)?$",
        r"github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
    raise ValueError(f"Invalid GitHub URL: {url}")


async def get_repo_default_branch(client: httpx.AsyncClient, owner: str, repo: str) -> str:
    """Get the default branch of a repo."""
    response = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers=get_github_headers(),
    )
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail=f"Repository not found: {owner}/{repo}")
    return response.json().get("default_branch", "main")


async def get_repo_tree(client: httpx.AsyncClient, owner: str, repo: str, branch: str) -> list[dict]:
    """Get the file tree of a repo."""
    response = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
        headers=get_github_headers(),
    )
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get repo tree")
    return response.json().get("tree", [])


async def get_file_content(client: httpx.AsyncClient, owner: str, repo: str, path: str, branch: str) -> str:
    """Get raw file content from GitHub."""
    headers = {}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    response = await client.get(
        f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}",
        headers=headers,
    )
    if response.status_code != 200:
        return ""
    return response.text


def get_code_context(content: str, line_num: int, context_lines: int = 3) -> str:
    """Extract code snippet with context around a specific line."""
    lines = content.split('\n')
    start = max(0, line_num - context_lines - 1)
    end = min(len(lines), line_num + context_lines)

    snippet_lines = []
    for i in range(start, end):
        prefix = ">>> " if i == line_num - 1 else "    "
        snippet_lines.append(f"{i + 1:4d} {prefix}{lines[i]}")

    return '\n'.join(snippet_lines)


@router.post("/analyze", response_model=RepoAnalyzeResponse)
async def analyze_repo(request: RepoAnalyzeRequest):
    """Analyze a public GitHub repository using HIGH-PRECISION detection only.

    This endpoint uses DETERMINISTIC pattern matching - not LLM guessing.
    Every finding has specific file:line:code evidence.
    Empty results ("No issues detected") are valid and honest.
    """
    try:
        owner, repo = parse_github_url(request.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.analyzers.high_precision_analyzer import HighPrecisionAnalyzer
    analyzer = HighPrecisionAnalyzer()

    async with httpx.AsyncClient(timeout=30.0) as client:
        branch = request.branch or await get_repo_default_branch(client, owner, repo)
        tree = await get_repo_tree(client, owner, repo, branch)

        # Filter analyzable files
        analyzable_extensions = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".php", ".rb", ".java", ".go",
            ".env", ".yaml", ".yml", ".json", ".sql", ".sh", ".rs", ".c", ".cpp",
            ".pem", ".key"
        }

        # Files that are always worth checking regardless of extension
        always_check = {".env", "Gemfile.lock", "package-lock.json", "composer.lock", "yarn.lock"}

        files_to_analyze = []
        for item in tree:
            if item["type"] != "blob":
                continue
            path = item["path"]
            filename = path.split("/")[-1]
            ext = "." + path.split(".")[-1] if "." in path else ""

            if ext in analyzable_extensions or filename in always_check:
                files_to_analyze.append(path)

        files_to_analyze = files_to_analyze[:100]  # Limit for performance

        # Analyze files and collect findings with REAL evidence
        all_findings: list[Finding] = []
        files_content: dict[str, str] = {}

        async def analyze_file(path: str) -> list[Finding]:
            findings = []
            try:
                content = await get_file_content(client, owner, repo, path, branch)
                if not content:
                    return []

                files_content[path] = content

                # Run high-precision analyzer
                raw_findings = analyzer.analyze_file(file_path=path, content=content)

                # Convert to our Finding format with ACTUAL code snippets
                for f in raw_findings:
                    # Use evidence.code_snippet if available, otherwise extract context
                    code_snippet = f.evidence.code_snippet or get_code_context(content, f.start_line)

                    findings.append(Finding(
                        severity=f.severity.value,
                        category=f.category.value,
                        file_path=f.file_path,
                        line_number=f.start_line,
                        code_snippet=code_snippet,
                        reason=f.evidence.rule_trigger_reason,
                        confidence="exact_match",  # Will be enhanced with confidence scoring
                        suggested_fix=get_fix_suggestion(f.category.value, f.evidence),
                    ))

                return findings
            except Exception as e:
                logger.warning(f"Failed to analyze {path}: {e}")
                return []

        # Process files in batches
        for i in range(0, len(files_to_analyze), 10):
            batch = files_to_analyze[i:i+10]
            results = await asyncio.gather(*[analyze_file(p) for p in batch])
            for findings in results:
                all_findings.extend(findings)

        # Count by severity
        critical_count = sum(1 for f in all_findings if f.severity == "critical")
        warning_count = sum(1 for f in all_findings if f.severity == "warning")
        info_count = sum(1 for f in all_findings if f.severity == "info")

        # Generate honest summary
        if not all_findings:
            summary = f"No high-risk issues detected in {len(files_to_analyze)} files. Scanned for: secrets, private keys, .env files, destructive migrations, auth middleware removal."
        else:
            parts = []
            if critical_count:
                parts.append(f"{critical_count} critical")
            if warning_count:
                parts.append(f"{warning_count} warning")
            if info_count:
                parts.append(f"{info_count} info")
            summary = f"Found {', '.join(parts)} issue(s) in {len(files_to_analyze)} files."

        return RepoAnalyzeResponse(
            repo=f"{owner}/{repo}",
            branch=branch,
            files_analyzed=len(files_to_analyze),
            summary=summary,
            findings=all_findings,
            critical_count=critical_count,
            warning_count=warning_count,
            info_count=info_count,
        )


def get_fix_suggestion(category: str, evidence) -> str:
    """Get specific fix suggestion based on category."""
    # Handle both Evidence dataclass and dict (for backwards compatibility)
    if hasattr(evidence, 'rule_name'):
        # Evidence dataclass
        rule_name = evidence.rule_name
        pattern_matched = evidence.pattern_matched or ""
    else:
        # dict (backwards compatibility)
        rule_name = evidence.get('pattern', evidence.get('name', 'issue'))
        pattern_matched = evidence.get('pattern', '')
    
    fixes = {
        "secret_exposure": f"Remove the {rule_name} from code. Use environment variables instead. Rotate this credential immediately as it may be compromised.",
        "private_key_exposed": "Remove private key from repository. Store in secure vault (HashiCorp Vault, AWS Secrets Manager). Regenerate the key as it's now compromised.",
        "env_leaked": "Remove .env file from repository. Add .env to .gitignore. Rotate any credentials that were exposed.",
        "migration_destructive": f"Review this {rule_name}. Ensure you have a backup strategy. Consider a reversible migration instead.",
        "auth_middleware_removed": f"Verify this route should be public. The authentication middleware was explicitly removed.",
        "dependency_changed": "Review dependency changes for security implications. Run `npm audit` or equivalent for your package manager.",
    }
    return fixes.get(category, "Review this finding and address if applicable.")


@router.post("/ask", response_model=AskRepoResponse)
async def ask_about_repo(request: AskRepoRequest):
    """Ask a question about a public GitHub repository.

    Uses LLM for answering questions (appropriate use of LLM - explanation, not detection).
    """
    try:
        owner, repo = parse_github_url(request.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    llm_service = LLMService()

    async with httpx.AsyncClient(timeout=30.0) as client:
        branch = await get_repo_default_branch(client, owner, repo)
        tree = await get_repo_tree(client, owner, repo, branch)

        if request.file_paths:
            files_to_read = request.file_paths[:10]
        else:
            code_extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".php", ".rb", ".java", ".go", ".rs"}
            config_files = {"README.md", "package.json", "requirements.txt", "composer.json", "Cargo.toml", "pyproject.toml"}

            files_to_read = []
            for item in tree:
                if item["type"] != "blob":
                    continue
                path = item["path"]
                ext = "." + path.split(".")[-1] if "." in path else ""
                filename = path.split("/")[-1]

                if filename in config_files or ext in code_extensions:
                    files_to_read.append(path)

            files_to_read.sort(key=lambda x: len(x.split("/")))
            files_to_read = files_to_read[:15]

        sources = []
        context_parts = []

        for path in files_to_read:
            content = await get_file_content(client, owner, repo, path, branch)
            if content:
                truncated = content[:4000] + "..." if len(content) > 4000 else content
                context_parts.append(f"### File: {path}\n```\n{truncated}\n```\n")
                sources.append({
                    "file_path": path,
                    "url": f"https://github.com/{owner}/{repo}/blob/{branch}/{path}",
                })

        context = "\n".join(context_parts)
        prompt = f"""Based on the following code files from {owner}/{repo}, answer this question:

Question: {request.question}

{context}

Provide a specific, accurate answer. Reference file paths and line numbers when relevant. If you cannot answer from the provided code, say so clearly."""

        answer = await llm_service.generate(
            prompt=prompt,
            max_tokens=1500,
            temperature=0.3,
            system_prompt="You are a code analyst. Answer questions based ONLY on the provided code. Be specific - reference files and lines. If unsure, say so.",
        )

        return AskRepoResponse(
            answer=answer,
            sources=sources,
        )


@router.get("/health")
async def test_health():
    """Health check for test routes."""
    return {"status": "ok", "message": "Test routes are working"}


# ============================================================================
# DEEP ANALYSIS ENDPOINTS
# ============================================================================

# Cache for analysis contexts (in-memory for demo, use Redis in production)
analysis_cache: dict[str, "AnalysisContext"] = {}


class DeepAnalyzeRequest(BaseModel):
    """Request for deep analysis."""
    repo_url: str
    branch: Optional[str] = None
    include_embeddings: bool = True


class SymbolInfo(BaseModel):
    """Symbol information."""
    type: str
    name: str
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None


class CoverageInfo(BaseModel):
    """Coverage tracking information."""
    total_files_discovered: int
    files_parsed_successfully: int
    files_skipped: dict[str, int]
    files_failed_parsing: int
    coverage_percentage: float
    languages_detected: dict[str, int]
    analyzer_coverage: dict[str, bool]
    is_incomplete: bool
    incomplete_reason: Optional[str] = None


class ScoringInfo(BaseModel):
    """Scoring and deduplication information."""
    total_raw_findings: int
    unique_findings: int
    deduplication_rate: float
    summary_breakdown: str


class IssueGroup(BaseModel):
    """Grouped issue information."""
    rule_id: str
    category: str
    count: int
    description: str


class DeepAnalyzeResponse(BaseModel):
    """Response from deep analysis with coverage, scoring, and evidence."""
    repo: str
    branch: str
    commit_sha: str
    detected_framework: str
    files_parsed: int
    total_symbols: int
    total_functions: int
    total_classes: int
    parse_errors: list[str]
    findings: list[Finding]
    critical_count: int
    warning_count: int
    info_count: int
    summary_breakdown: str  # Human-readable summary of unique issues
    deduplication_stats: ScoringInfo
    issue_groups: dict[str, IssueGroup]  # Grouped by rule_id:category
    coverage: CoverageInfo
    top_level_symbols: list[SymbolInfo]
    entry_points: list[SymbolInfo]
    qa_ready: bool
    chunks_indexed: int


class DeepAskRequest(BaseModel):
    """Request to ask about a deeply analyzed repo."""
    repo_url: str
    question: str


class CitedSource(BaseModel):
    """A source with citation and validation status."""
    index: int
    file_path: str
    line_start: int
    line_end: int
    symbol_name: Optional[str]
    code_snippet: str
    url: str
    validation_status: Optional[str] = None  # verified | unverified | failed


class AnswerSection(BaseModel):
    """Section of answer with sources."""
    text: str
    source_indices: list[int]


class DeepAskResponse(BaseModel):
    """Response with evidence-backed answer and validation status."""
    answer_text: str
    sections: list[AnswerSection]
    unknowns: list[str]
    sources: list[CitedSource]
    confidence: str
    call_graph_context: Optional[list[str]] = None
    validation_status: Optional[str] = None  # verified | partially_verified | failed
    unsupported_claims: Optional[list[str]] = None  # Claims that couldn't be verified


@router.post("/deep-analyze", response_model=DeepAnalyzeResponse)
async def deep_analyze_repo(request: DeepAnalyzeRequest):
    """
    Deep analysis: clone, parse AST, build indexes, run analyzers.

    This gives Claude Code-level understanding of the codebase:
    - Clones repo locally
    - Parses with tree-sitter (AST)
    - Builds symbol table, call graph, dependency graph
    - Runs deterministic security analyzers
    - Generates embeddings for semantic Q&A
    """
    from app.services.deep_analysis_service import DeepAnalysisService

    service = DeepAnalysisService()

    try:
        result = await service.analyze_repository(
            repo_url=request.repo_url,
            branch=request.branch,
            include_embeddings=request.include_embeddings,
            token=settings.github_token if settings.github_token else None,
        )

        # Cache context for follow-up questions
        cache_key = f"{request.repo_url}:{request.branch or 'default'}"
        analysis_cache[cache_key] = result["context"]

        # Limit cache size
        if len(analysis_cache) > 10:
            oldest_key = next(iter(analysis_cache))
            old_context = analysis_cache.pop(oldest_key)
            service.cleanup(old_context)

        return DeepAnalyzeResponse(**result["response"])

    except Exception as e:
        logger.exception(f"Deep analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deep-ask", response_model=DeepAskResponse)
async def deep_ask_question(request: DeepAskRequest):
    """
    Ask a question using deep code understanding.

    Uses semantic search + symbol table + call graph to find relevant code,
    then sends to LLM with strict citation requirements.

    Requires /deep-analyze to be called first for the same repo.
    """
    from app.services.deep_analysis_service import DeepAnalysisService

    # Find cached context
    cache_key = f"{request.repo_url}:default"
    context = None

    # Try to find matching cache
    for key, ctx in analysis_cache.items():
        if request.repo_url in key:
            context = ctx
            break

    if not context:
        raise HTTPException(
            status_code=400,
            detail="Repository not analyzed. Call /deep-analyze first."
        )

    service = DeepAnalysisService()

    try:
        result = await service.answer_question(context, request.question)

        return DeepAskResponse(
            answer_text=result["answer_text"],
            sections=[AnswerSection(**s) for s in result.get("sections", [])],
            unknowns=result.get("unknowns", []),
            sources=[CitedSource(**s) for s in result.get("sources", [])],
            confidence=result.get("confidence", "low"),
            call_graph_context=result.get("call_graph_context"),
        )

    except Exception as e:
        logger.exception(f"Deep ask failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/deep-analyze/{cache_key}")
async def cleanup_analysis(cache_key: str):
    """Cleanup a cached analysis context."""
    from app.services.deep_analysis_service import DeepAnalysisService

    if cache_key in analysis_cache:
        context = analysis_cache.pop(cache_key)
        service = DeepAnalysisService()
        service.cleanup(context)
        return {"status": "cleaned", "key": cache_key}

    return {"status": "not_found", "key": cache_key}


@router.get("/deep-analyze/status")
async def get_analysis_status():
    """Get status of cached analyses."""
    return {
        "cached_analyses": len(analysis_cache),
        "repos": list(analysis_cache.keys()),
    }


# ============================================================================
# COMPLIANCE ANALYSIS ENDPOINTS
# ============================================================================

class ComplianceAnalyzeRequest(BaseModel):
    """Request for compliance analysis."""
    repo_url: str
    region: str  # eu, us, uk, india, australia, canada, brazil, singapore, uae, global
    sector: str  # healthcare, finance, ecommerce, education, government, saas, social_media, iot, ai_ml, general


class RegulationInfo(BaseModel):
    """Regulation information."""
    code: str
    name: str
    description: str
    key_requirements: list[str]
    penalties: str
    official_url: str


class ComplianceFindingInfo(BaseModel):
    """A compliance finding."""
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


class ComplianceAnalyzeResponse(BaseModel):
    """Response from compliance analysis."""
    region: str
    sector: str
    applicable_regulations: list[RegulationInfo]
    findings: list[ComplianceFindingInfo]
    summary: dict
    ai_analysis: str
    recommendations: list[str]
    compliance_score: float
    risk_level: str


class RegulationResearchRequest(BaseModel):
    """Request for regulation research."""
    region: str
    sector: str


class RegulationResearchResponse(BaseModel):
    """Response with regulation research."""
    regulations: list[RegulationInfo]
    research: str


@router.post("/compliance/analyze", response_model=ComplianceAnalyzeResponse)
async def analyze_compliance(request: ComplianceAnalyzeRequest):
    """
    Analyze code for regulatory compliance.

    Based on target deployment region and industry sector, checks for:
    - GDPR, CCPA, HIPAA, PCI-DSS, SOC2, DPDP, LGPD, PDPA compliance
    - Data privacy requirements
    - Security standards
    - Industry-specific regulations

    Requires /deep-analyze to be called first for the same repo.
    """
    from app.services.compliance_service import ComplianceService

    # Find cached context
    context = None
    for key, ctx in analysis_cache.items():
        if request.repo_url in key:
            context = ctx
            break

    if not context:
        raise HTTPException(
            status_code=400,
            detail="Repository not analyzed. Call /deep-analyze first."
        )

    service = ComplianceService()

    try:
        # Get code files from cached context
        code_files = {}
        if hasattr(context, 'parse_result') and context.parse_result:
            # Build code files from symbols
            for symbol in context.parse_result.symbols:
                if symbol.body and symbol.file_path not in code_files:
                    code_files[symbol.file_path] = symbol.body

        # If no code from symbols, try to read from repo path
        if not code_files and hasattr(context, 'repo_path') and context.repo_path:
            import os
            for root, _, files in os.walk(context.repo_path):
                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.tsx', '.jsx', '.php', '.rb', '.java', '.go')):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, context.repo_path)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                code_files[rel_path] = f.read()
                        except Exception:
                            pass

        # Run compliance analysis
        report = await service.analyze_compliance(
            code_files=code_files,
            region=request.region,
            sector=request.sector,
            symbols=context.parse_result.symbols if hasattr(context, 'parse_result') else None,
        )

        return ComplianceAnalyzeResponse(
            region=report.region,
            sector=report.sector,
            applicable_regulations=[
                RegulationInfo(
                    code=r.code,
                    name=r.name,
                    description=r.description,
                    key_requirements=r.key_requirements,
                    penalties=r.penalties,
                    official_url=r.official_url,
                )
                for r in report.applicable_regulations
            ],
            findings=[
                ComplianceFindingInfo(
                    check_id=f.check_id,
                    regulation=f.regulation,
                    category=f.category,
                    severity=f.severity,
                    title=f.title,
                    description=f.description,
                    file_path=f.file_path,
                    line_start=f.line_start,
                    line_end=f.line_end,
                    code_snippet=f.code_snippet,
                    recommendation=f.recommendation,
                    reference_url=f.reference_url,
                )
                for f in report.findings
            ],
            summary=report.summary,
            ai_analysis=report.ai_analysis,
            recommendations=report.recommendations,
            compliance_score=report.compliance_score,
            risk_level=report.risk_level,
        )

    except Exception as e:
        logger.exception(f"Compliance analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance/research", response_model=RegulationResearchResponse)
async def research_regulations(request: RegulationResearchRequest):
    """
    Research applicable regulations for a region and sector.

    Uses AI to provide up-to-date information about:
    - Applicable laws and regulations
    - Key requirements
    - Recent updates
    - Upcoming regulations
    """
    from app.services.compliance_service import ComplianceService

    service = ComplianceService()

    try:
        result = await service.research_regulations(
            region=request.region,
            sector=request.sector,
        )

        return RegulationResearchResponse(
            regulations=[
                RegulationInfo(
                    code=r.code,
                    name=r.name,
                    description=r.description,
                    key_requirements=r.key_requirements,
                    penalties=r.penalties,
                    official_url=r.official_url,
                )
                for r in result["regulations"]
            ],
            research=result["research"],
        )

    except Exception as e:
        logger.exception(f"Regulation research failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compliance/regions")
async def get_available_regions():
    """Get list of supported deployment regions."""
    from app.services.compliance_service import Region
    return {
        "regions": [
            {"code": r.value, "name": r.name.replace("_", " ").title()}
            for r in Region
        ]
    }


@router.get("/compliance/sectors")
async def get_available_sectors():
    """Get list of supported industry sectors."""
    from app.services.compliance_service import IndustrySector
    return {
        "sectors": [
            {"code": s.value, "name": s.name.replace("_", " ").title()}
            for s in IndustrySector
        ]
    }


# ============================================================================
# CODEBASE DOCUMENTATION ENDPOINTS
# ============================================================================

class GenerateDocsRequest(BaseModel):
    """Request to generate AI-ready documentation."""
    repo_url: str


class GenerateDocsResponse(BaseModel):
    """Response with generated documentation."""
    codebase_md: str
    architecture_md: str
    symbol_map_md: str
    ai_context_json: str


@router.post("/docs/generate", response_model=GenerateDocsResponse)
async def generate_codebase_docs(request: GenerateDocsRequest):
    """
    Generate AI-ready documentation for a codebase.

    Creates structured documentation that helps AI assistants
    (Claude Code, Cursor, Copilot) understand and navigate the codebase:

    - CODEBASE.md: High-level overview
    - ARCHITECTURE.md: System design
    - SYMBOL_MAP.md: Symbol reference
    - .ai/context.json: Machine-readable context
    """
    from app.services.codebase_doc_service import CodebaseDocService

    # Find cached context
    context = None
    for key, ctx in analysis_cache.items():
        if request.repo_url in key:
            context = ctx
            break

    if not context:
        raise HTTPException(
            status_code=400,
            detail="Repository not analyzed. Call /deep-analyze first."
        )

    service = CodebaseDocService()

    try:
        docs = service.generate_all_docs(
            repo_path=context.repo_path if hasattr(context, 'repo_path') else "",
            repo_url=request.repo_url,
            parse_result=context.parse_result if hasattr(context, 'parse_result') else None,
            index=context.index if hasattr(context, 'index') else None,
            framework=context.detected_framework if hasattr(context, 'detected_framework') else "unknown",
        )

        return GenerateDocsResponse(
            codebase_md=docs.get("CODEBASE.md", ""),
            architecture_md=docs.get("ARCHITECTURE.md", ""),
            symbol_map_md=docs.get("SYMBOL_MAP.md", ""),
            ai_context_json=docs.get(".ai/context.json", "{}"),
        )

    except Exception as e:
        logger.exception(f"Documentation generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
