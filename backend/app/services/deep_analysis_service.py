"""Service for deep code analysis with local cloning and AST parsing."""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from app.config import get_settings
from app.services.clone_service import CloneService, CloneError
from app.services.parser_service import ParserService, ParseResult, Symbol
from app.services.index_service import IndexService, CodeIndex
from app.services.embedding_service import EmbeddingService, CodeChunk
from app.services.llm_service import LLMService
from app.analyzers.high_precision_analyzer import HighPrecisionAnalyzer

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class AnalysisContext:
    """Context for deep analysis - passed to Q&A."""
    repo_url: str
    repo_path: str
    branch: str
    commit_sha: str
    parse_result: ParseResult
    index: CodeIndex
    chunks: list[CodeChunk]
    detected_framework: str


@dataclass
class Finding:
    """A specific, evidence-based finding."""
    severity: str  # critical, warning, info
    category: str
    file_path: str
    line_number: int
    code_snippet: str
    reason: str
    confidence: str
    suggested_fix: Optional[str] = None


class DeepAnalysisService:
    """Service for deep code analysis."""

    def __init__(self):
        self.clone_service = CloneService()
        self.parser_service = ParserService()
        self.index_service = IndexService()
        self.embedding_service = EmbeddingService()
        self.analyzer = HighPrecisionAnalyzer()
        self.llm_service = LLMService()
        from app.services.scoring_service import ScoringService
        self.scoring_service = ScoringService()
        from app.services.coverage_service import CoverageService
        self.coverage_service = CoverageService()
        self.llm_service = LLMService()

    async def analyze_repository(
        self,
        repo_url: str,
        branch: Optional[str] = None,
        include_embeddings: bool = True,
        token: Optional[str] = None
    ) -> dict:
        """
        Full deep analysis of a repository.

        Steps:
        1. Clone repo locally
        2. Parse all files with tree-sitter
        3. Build symbol table, call graph, dependency graph
        4. Run deterministic analyzers on AST
        5. Optionally generate embeddings for Q&A
        6. Return complete analysis
        """
        repo_path = None

        try:
            # Use configured token if not provided
            if not token:
                token = settings.github_token if hasattr(settings, 'github_token') else None

            # Step 1: Clone repository
            logger.info(f"Step 1: Cloning {repo_url}")
            repo_path, commit_sha = await self.clone_service.clone_repo(
                repo_url=repo_url,
                branch=branch,
                token=token,
            )

            # Step 2: Discover files and parse all code files
            logger.info("Step 2: Discovering files")
            self.coverage_service.discover_files(repo_path)
            logger.info("Step 2: Parsing code with tree-sitter")
            parse_result = self.parser_service.parse_repository(repo_path, self.coverage_service)
            
            # Record analyzer coverage
            self.coverage_service.record_analyzer_run("SAST")
            self.coverage_service.record_analyzer_run("secrets")
            # Dependencies and IaC analyzers would be recorded if they run

            # Step 3: Build indexes
            logger.info("Step 3: Building symbol table and graphs")
            index = self.index_service.build_index(parse_result, repo_path)

            # Step 4: Run deterministic analyzers
            logger.info("Step 4: Running deterministic analyzers")
            findings, scoring_metadata = self._run_analyzers(repo_path, parse_result)
            self.coverage_service.record_analyzer_run("secrets")  # High-precision analyzer includes secrets

            # Step 5: Generate embeddings (optional)
            chunks = []
            if include_embeddings:
                logger.info("Step 5: Generating embeddings for Q&A")
                chunks = self.embedding_service.chunk_code(parse_result.symbols, repo_path)
                chunks = await self.embedding_service.generate_embeddings(chunks)
            else:
                logger.info("Step 5: Skipping embeddings (disabled)")
                chunks = self.embedding_service.chunk_code(parse_result.symbols, repo_path)

            # Detect framework
            framework = self._detect_framework(parse_result, repo_path)

            # Build context for Q&A
            context = AnalysisContext(
                repo_url=repo_url,
                repo_path=repo_path,
                branch=branch or "default",
                commit_sha=commit_sha,
                parse_result=parse_result,
                index=index,
                chunks=chunks,
                detected_framework=framework,
            )

            # Compute coverage report
            coverage_report = self.coverage_service.compute_coverage()
            
            # Build response
            owner_repo = self._extract_owner_repo(repo_url)
            top_symbols = self.index_service.get_top_level_symbols(index, limit=10)
            entry_points = self.index_service.get_entry_points(index)

            # Count findings
            critical_count = sum(1 for f in findings if f.severity == "critical")
            warning_count = sum(1 for f in findings if f.severity == "warning")
            info_count = sum(1 for f in findings if f.severity == "info")

            response = {
                "repo": owner_repo,
                "branch": branch or "default",
                "commit_sha": commit_sha,
                "detected_framework": framework,
                "files_parsed": parse_result.files_parsed,
                "total_symbols": index.total_symbols,
                "total_functions": index.total_functions,
                "total_classes": index.total_classes,
                "parse_errors": parse_result.parse_errors[:10],  # Limit errors shown
                "findings": [self._finding_to_dict(f) for f in findings],
                "critical_count": critical_count,
                "warning_count": warning_count,
                "info_count": info_count,
                "summary_breakdown": scoring_metadata["summary_breakdown"],
                "deduplication_stats": {
                    "total_raw_findings": scoring_metadata["total_raw_findings"],
                    "unique_findings": scoring_metadata["unique_findings"],
                    "deduplication_rate": scoring_metadata["deduplication_rate"],
                    "summary_breakdown": scoring_metadata["summary_breakdown"],
                },
                "issue_groups": scoring_metadata["groups"],
                "top_level_symbols": [self._symbol_to_dict(s) for s in top_symbols[:10]],
                "entry_points": [self._symbol_to_dict(s) for s in entry_points[:10]],
                "qa_ready": len(chunks) > 0,
                "chunks_indexed": len(chunks),
                "coverage": {
                    "total_files_discovered": coverage_report.total_files_discovered,
                    "files_parsed_successfully": coverage_report.files_parsed_successfully,
                    "files_skipped": coverage_report.files_skipped,
                    "files_failed_parsing": coverage_report.files_failed_parsing,
                    "coverage_percentage": coverage_report.coverage_percentage,
                    "languages_detected": coverage_report.languages_detected,
                    "analyzer_coverage": coverage_report.analyzer_coverage,
                    "is_incomplete": coverage_report.is_incomplete,
                    "incomplete_reason": coverage_report.incomplete_reason,
                },
            }

            return {
                "response": response,
                "context": context,
            }

        except CloneError as e:
            logger.error(f"Clone failed: {e}")
            raise
        except Exception as e:
            logger.exception(f"Analysis failed: {e}")
            raise
        finally:
            # Don't cleanup here - let caller handle it after Q&A
            pass

    def _run_analyzers(self, repo_path: str, parse_result: ParseResult) -> tuple[list[Finding], dict]:
        """Run deterministic analyzers on parsed code.
        
        Returns:
            tuple of (findings list, scoring metadata dict)
        """
        from app.analyzers.high_precision_analyzer import Finding as AnalyzerFinding
        
        raw_analyzer_findings = []

        # Run high-precision analyzer on each file
        for symbol in parse_result.symbols:
            if not symbol.body:
                continue

            try:
                import os
                file_path = os.path.join(repo_path, symbol.file_path)
                
                # Read full file content for context
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()

                # Run analyzer
                file_findings = self.analyzer.analyze_file(
                    file_path=symbol.file_path,
                    content=content
                )
                raw_analyzer_findings.extend(file_findings)

            except Exception as e:
                logger.warning(f"Analyzer failed for {symbol.file_path}: {e}")

        # Deduplicate and score findings using ScoringService
        deduplicated = self.scoring_service.deduplicate_findings(raw_analyzer_findings)
        scored_findings = self.scoring_service.score_findings(deduplicated)
        groups = self.scoring_service.group_by_issue_type(scored_findings)
        summary_breakdown = self.scoring_service.create_summary_breakdown(groups)

        # Convert scored findings to local Finding format
        findings = []
        for scored in scored_findings:
            rf = scored.finding
            code_snippet = rf.evidence.code_snippet or ""
            
            findings.append(Finding(
                severity=rf.severity.value,
                category=rf.category.value,
                file_path=rf.file_path,
                line_number=rf.start_line,
                code_snippet=code_snippet,
                reason=rf.evidence.rule_trigger_reason,
                confidence=scored.confidence.level,  # Use scored confidence level
                suggested_fix=self._get_fix_suggestion(rf.category.value, rf.evidence),
            ))

        # Build scoring metadata
        scoring_metadata = {
            "total_raw_findings": len(raw_analyzer_findings),
            "unique_findings": len(scored_findings),
            "deduplication_rate": len(scored_findings) / len(raw_analyzer_findings) if raw_analyzer_findings else 0,
            "summary_breakdown": summary_breakdown,
            "groups": {
                key: {
                    "rule_id": group.rule_id,
                    "category": group.category,
                    "count": group.unique_count,
                    "description": group.description,
                }
                for key, group in groups.items()
            }
        }

        return findings, scoring_metadata

    def _get_code_context(self, content: str, line_num: int, context_lines: int = 3) -> str:
        """Extract code snippet with context around a specific line."""
        lines = content.split('\n')
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)

        snippet_lines = []
        for i in range(start, end):
            prefix = ">>> " if i == line_num - 1 else "    "
            snippet_lines.append(f"{i + 1:4d} {prefix}{lines[i]}")

        return '\n'.join(snippet_lines)

    def _get_fix_suggestion(self, category: str, evidence: dict) -> str:
        """Get specific fix suggestion based on category."""
        fixes = {
            "secret_exposure": f"Remove the secret from code. Use environment variables instead. Rotate this credential immediately.",
            "private_key_exposed": "Remove private key from repository. Store in secure vault. Regenerate the key.",
            "env_leaked": "Remove .env file from repository. Add .env to .gitignore. Rotate exposed credentials.",
            "migration_destructive": f"Review this destructive operation. Ensure backup strategy. Consider reversible migration.",
            "auth_middleware_removed": "Verify this route should be public. The auth middleware was explicitly removed.",
            "dependency_changed": "Review dependency changes for security implications. Run security audit.",
        }
        return fixes.get(category, "Review this finding and address if applicable.")

    def _detect_framework(self, parse_result: ParseResult, repo_path: str) -> str:
        """Detect the main framework used in the repository."""
        import os

        # Check for common framework indicators
        indicators = {
            "laravel": ["artisan", "app/Http/Controllers", "routes/web.php"],
            "django": ["manage.py", "wsgi.py", "settings.py"],
            "fastapi": ["main.py", "uvicorn"],
            "flask": ["app.py", "flask"],
            "express": ["package.json", "express"],
            "nextjs": ["next.config", "_app.tsx", "_app.js"],
            "react": ["package.json", "react-dom"],
            "vue": ["vue.config.js", "nuxt.config"],
            "rails": ["Gemfile", "config/routes.rb"],
            "spring": ["pom.xml", "build.gradle"],
        }

        files = set()
        for symbol in parse_result.symbols:
            files.add(symbol.file_path)

        for imp in parse_result.imports:
            files.add(imp.file_path)

        # Check file indicators
        for framework, patterns in indicators.items():
            for pattern in patterns:
                for f in files:
                    if pattern.lower() in f.lower():
                        return framework

        # Check imports
        for imp in parse_result.imports:
            module_lower = imp.module.lower()
            if "fastapi" in module_lower:
                return "fastapi"
            elif "flask" in module_lower:
                return "flask"
            elif "django" in module_lower:
                return "django"
            elif "express" in module_lower:
                return "express"
            elif "next" in module_lower:
                return "nextjs"
            elif "react" in module_lower:
                return "react"

        return "unknown"

    def _extract_owner_repo(self, repo_url: str) -> str:
        """Extract owner/repo from URL."""
        patterns = [
            r"github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/.*)?$",
            r"github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        ]
        for pattern in patterns:
            match = re.search(pattern, repo_url)
            if match:
                return f"{match.group(1)}/{match.group(2).rstrip('.git')}"
        return repo_url

    def _symbol_to_dict(self, symbol: Symbol) -> dict:
        """Convert Symbol to dict for JSON response."""
        return {
            "type": symbol.type,
            "name": symbol.name,
            "file_path": symbol.file_path,
            "line_start": symbol.line_start,
            "line_end": symbol.line_end,
            "signature": symbol.signature,
        }

    def _finding_to_dict(self, finding: Finding) -> dict:
        """Convert Finding to dict for JSON response."""
        return {
            "severity": finding.severity,
            "category": finding.category,
            "file_path": finding.file_path,
            "line_number": finding.line_number,
            "code_snippet": finding.code_snippet,
            "reason": finding.reason,
            "confidence": finding.confidence,
            "suggested_fix": finding.suggested_fix,
        }

    async def answer_question(
        self,
        context: AnalysisContext,
        question: str
    ) -> dict:
        """
        Answer a question using deep code understanding.

        Steps:
        1. Search embeddings for relevant code
        2. Search symbol table for mentioned names
        3. Get call graph context for found symbols
        4. Build focused context with actual code
        5. Send to LLM with citation requirements
        6. Validate citations exist
        7. Return answer with evidence
        """
        # Step 1 & 2: Find relevant code
        relevant_chunks = await self._find_relevant_code(context, question)

        if not relevant_chunks:
            return {
                "answer_text": "I couldn't find relevant code to answer this question.",
                "sections": [],
                "unknowns": [question],
                "sources": [],
                "confidence": "insufficient",
                "call_graph_context": None,
            }

        # Step 3: Get call graph context
        call_chains = []
        for chunk, _ in relevant_chunks[:3]:
            if chunk.symbol_name:
                chains = self.index_service.trace_flow(
                    context.index,
                    f"{chunk.file_path}:{chunk.symbol_name}",
                    max_depth=3
                )
                call_chains.extend(chains[:2])

        # Step 4: Build LLM context
        llm_context = self._build_llm_context(relevant_chunks, context)

        # Step 5: Send to LLM
        owner_repo = self._extract_owner_repo(context.repo_url)
        
        prompt = f"""Based on the following code from {owner_repo}, answer this question:

Question: {question}

{llm_context}

Instructions:
1. Answer based ONLY on the provided code sources
2. Reference sources by their [SOURCE N] numbers
3. Be specific - mention exact function/class names
4. If you cannot answer from the code, say so clearly
5. Structure your answer with clear sections if needed

Format your response as JSON:
{{
  "sections": [
    {{"text": "...", "source_indices": [1, 2]}}
  ],
  "unknowns": ["things you couldn't answer from the code"],
  "summary": "brief 1-2 sentence summary"
}}"""

        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.3,
                system_prompt="You are a code analyst. Answer ONLY from provided code. Output valid JSON.",
            )

            # Parse LLM response
            parsed = self._parse_llm_response(response)

            # Step 6: Validate citations
            valid_sources = []
            for chunk, score in relevant_chunks:
                valid_sources.append({
                    "index": len(valid_sources) + 1,
                    "file_path": chunk.file_path,
                    "line_start": chunk.line_start,
                    "line_end": chunk.line_end,
                    "symbol_name": chunk.symbol_name,
                    "code_snippet": chunk.content[:500] + "..." if len(chunk.content) > 500 else chunk.content,
                    "url": f"https://github.com/{owner_repo}/blob/{context.branch}/{chunk.file_path}#L{chunk.line_start}",
                })

            # Determine confidence
            confidence = self._determine_confidence(parsed, valid_sources)

            # Build answer text
            answer_text = parsed.get("summary", "")
            for section in parsed.get("sections", []):
                answer_text += "\n\n" + section.get("text", "")

            return {
                "answer_text": answer_text.strip(),
                "sections": parsed.get("sections", []),
                "unknowns": parsed.get("unknowns", []),
                "sources": valid_sources,
                "confidence": confidence,
                "call_graph_context": [" -> ".join(chain) for chain in call_chains[:5]] if call_chains else None,
            }

        except Exception as e:
            logger.error(f"LLM answer generation failed: {e}")
            return {
                "answer_text": f"Error generating answer: {str(e)}",
                "sections": [],
                "unknowns": [question],
                "sources": [],
                "confidence": "insufficient",
                "call_graph_context": None,
            }

    async def _find_relevant_code(
        self,
        context: AnalysisContext,
        question: str,
        max_chunks: int = 10
    ) -> list[tuple[CodeChunk, float]]:
        """Find code relevant to the question."""
        results = []

        # Semantic search if embeddings available
        if any(c.embedding for c in context.chunks):
            results = await self.embedding_service.search_async(
                query=question,
                chunks=context.chunks,
                top_k=max_chunks
            )
        else:
            # Keyword search fallback
            results = self.embedding_service._keyword_search(
                query=question,
                chunks=context.chunks,
                top_k=max_chunks
            )

        # Also search symbol table for mentioned names
        words = question.lower().split()
        for word in words:
            if len(word) > 3:  # Skip short words
                symbols = self.index_service.find_symbol(context.index, word)
                for sym in symbols[:3]:
                    # Find corresponding chunk
                    for chunk in context.chunks:
                        if chunk.symbol_name == sym.name and chunk.file_path == sym.file_path:
                            if chunk not in [r[0] for r in results]:
                                results.append((chunk, 0.5))  # Medium relevance score
                            break

        return results[:max_chunks]

    def _build_llm_context(
        self,
        chunks: list[tuple[CodeChunk, float]],
        context: AnalysisContext
    ) -> str:
        """Build context string for LLM with numbered sources."""
        parts = []

        for i, (chunk, score) in enumerate(chunks, 1):
            parts.append(f"[SOURCE {i}] {chunk.file_path}:{chunk.line_start}-{chunk.line_end}")
            if chunk.symbol_name:
                parts.append(f"Symbol: {chunk.symbol_type} {chunk.symbol_name}")
            parts.append("```")
            parts.append(chunk.content)
            parts.append("```\n")

        return "\n".join(parts)

    def _parse_llm_response(self, response: str) -> dict:
        """Parse LLM JSON response."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        # Fallback: treat as plain text
        return {
            "sections": [{"text": response, "source_indices": []}],
            "unknowns": [],
            "summary": response[:200] if len(response) > 200 else response,
        }

    def _determine_confidence(self, parsed: dict, sources: list) -> str:
        """Determine confidence level based on citations."""
        sections = parsed.get("sections", [])
        total_citations = sum(len(s.get("source_indices", [])) for s in sections)
        unique_sources = set()
        for s in sections:
            unique_sources.update(s.get("source_indices", []))

        unknowns = parsed.get("unknowns", [])

        if len(unknowns) > 0 and total_citations == 0:
            return "insufficient"
        elif total_citations >= 3 and len(unique_sources) >= 2:
            return "high"
        elif total_citations >= 1:
            return "medium"
        else:
            return "low"

    def cleanup(self, context: AnalysisContext) -> None:
        """Cleanup cloned repository after analysis."""
        if context and context.repo_path:
            self.clone_service.cleanup(context.repo_path)
