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

from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter()


class RepoAnalyzeRequest(BaseModel):
    """Request to analyze a GitHub repo."""
    repo_url: str
    branch: Optional[str] = None


class Finding(BaseModel):
    """A specific, evidence-based finding."""
    severity: str  # critical, warning, info
    category: str
    file_path: str
    line_number: int
    code_snippet: str  # Actual code from the file
    reason: str  # Specific reason, not generic
    confidence: str  # exact_match, structural, pattern
    suggested_fix: Optional[str] = None


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
        headers={"Accept": "application/vnd.github.v3+json"},
    )
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail=f"Repository not found: {owner}/{repo}")
    return response.json().get("default_branch", "main")


async def get_repo_tree(client: httpx.AsyncClient, owner: str, repo: str, branch: str) -> list[dict]:
    """Get the file tree of a repo."""
    response = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
        headers={"Accept": "application/vnd.github.v3+json"},
    )
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get repo tree")
    return response.json().get("tree", [])


async def get_file_content(client: httpx.AsyncClient, owner: str, repo: str, path: str, branch: str) -> str:
    """Get raw file content from GitHub."""
    response = await client.get(
        f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}",
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
                    code_snippet = get_code_context(content, f.start_line)

                    findings.append(Finding(
                        severity=f.severity.value,
                        category=f.category.value,
                        file_path=f.file_path,
                        line_number=f.start_line,
                        code_snippet=code_snippet,
                        reason=f.evidence.get("reason", f.evidence.get("pattern", "")),
                        confidence=f.evidence.get("confidence", "exact_match"),
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


def get_fix_suggestion(category: str, evidence: dict) -> str:
    """Get specific fix suggestion based on category."""
    fixes = {
        "secret_exposure": f"Remove the {evidence.get('pattern', 'secret')} from code. Use environment variables instead. Rotate this credential immediately as it may be compromised.",
        "private_key_exposed": "Remove private key from repository. Store in secure vault (HashiCorp Vault, AWS Secrets Manager). Regenerate the key as it's now compromised.",
        "env_leaked": "Remove .env file from repository. Add .env to .gitignore. Rotate any credentials that were exposed.",
        "migration_destructive": f"Review this {evidence.get('operation', 'destructive operation')}. Ensure you have a backup strategy. Consider a reversible migration instead.",
        "auth_middleware_removed": f"Verify this route should be public. The '{evidence.get('middleware', 'auth')}' middleware was explicitly removed.",
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
