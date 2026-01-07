"""Coverage tracking service for code analysis.

Tracks which files were discovered, parsed, skipped, and which analyzers ran
to provide transparency about scan coverage.
"""

import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CoverageReport:
    """Coverage report for code analysis."""

    total_files_discovered: int
    files_parsed_successfully: int
    files_skipped: dict[str, int] = field(default_factory=dict)  # reason -> count
    files_failed_parsing: int = 0
    coverage_percentage: float = 0.0
    languages_detected: dict[str, int] = field(default_factory=dict)  # language -> count
    analyzer_coverage: dict[str, bool] = field(default_factory=dict)  # analyzer -> ran
    parse_errors: list[str] = field(default_factory=list)
    files_discoverable: int = 0  # Files that could be parsed (non-binary, supported languages)
    is_incomplete: bool = False
    incomplete_reason: Optional[str] = None


class CoverageService:
    """Service for tracking analysis coverage."""

    # File extensions that indicate binary files
    BINARY_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".bmp", ".webp",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
        ".mp3", ".mp4", ".avi", ".mov", ".wmv", ".flv",
        ".exe", ".dll", ".so", ".dylib", ".bin",
        ".woff", ".woff2", ".ttf", ".eot", ".otf",
        ".db", ".sqlite", ".sqlite3",
    }

    # Languages we can parse
    PARSEABLE_LANGUAGES = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".php": "php",
        ".rb": "ruby",
        ".go": "go",
        ".java": "java",
        ".rs": "rust",
        ".c": "c",
        ".cpp": "cpp",
        ".cs": "csharp",
    }

    # Directories to skip
    SKIP_DIRS = {
        ".git", "__pycache__", ".venv", "venv", "node_modules",
        "vendor", "dist", "build", ".next", ".nuxt", "coverage",
        ".pytest_cache", ".mypy_cache", "eggs", ".eggs",
    }

    # Files to skip
    SKIP_FILES = {".min.js", ".bundle.js", ".map"}

    MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB

    def __init__(self):
        self.files_discovered: list[str] = []
        self.files_parsed: list[str] = []
        self.files_skipped: dict[str, list[str]] = defaultdict(list)  # reason -> files
        self.files_failed: list[tuple[str, str]] = []  # (file, error)
        self.languages: dict[str, int] = defaultdict(int)
        self.analyzers_run: set[str] = set()

    def discover_files(self, repo_path: str) -> int:
        """Discover all files in repository.
        
        Returns count of total files discovered.
        """
        self.files_discovered = []
        
        for root, dirs, files in os.walk(repo_path):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            
            for filename in files:
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, repo_path)
                self.files_discovered.append(rel_path)
        
        return len(self.files_discovered)

    def should_skip_file(self, file_path: str, file_size: Optional[int] = None) -> Optional[str]:
        """Check if file should be skipped and return reason if so."""
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        path_lower = file_path.lower()

        # Check file size
        if file_size and file_size > self.MAX_FILE_SIZE:
            return "too_large"

        # Check if binary
        if ext in self.BINARY_EXTENSIONS:
            return "binary"

        # Check skip patterns
        for skip_file in self.SKIP_FILES:
            if filename.endswith(skip_file):
                return "minified_or_bundle"

        # Check directory patterns
        for skip_dir in self.SKIP_DIRS:
            if f"/{skip_dir}/" in path_lower or path_lower.startswith(skip_dir + "/"):
                return f"vendor_or_build_dir"

        # Check if unsupported language
        if ext not in self.PARSEABLE_LANGUAGES:
            # Allow config files even if not parseable
            config_extensions = {".json", ".yaml", ".yml", ".toml", ".ini", ".env", ".txt", ".md"}
            if ext not in config_extensions:
                return "unsupported_language"

        return None

    def record_file_parsed(self, file_path: str, language: Optional[str] = None):
        """Record that a file was successfully parsed."""
        self.files_parsed.append(file_path)
        if language:
            self.languages[language] += 1

    def record_file_skipped(self, file_path: str, reason: str):
        """Record that a file was skipped."""
        self.files_skipped[reason].append(file_path)

    def record_parse_error(self, file_path: str, error: str):
        """Record a parse error."""
        self.files_failed.append((file_path, error))

    def record_analyzer_run(self, analyzer_name: str):
        """Record that an analyzer ran."""
        self.analyzers_run.add(analyzer_name)

    def compute_coverage(self) -> CoverageReport:
        """Compute coverage statistics."""
        total_discovered = len(self.files_discovered)
        parsed = len(self.files_parsed)
        failed = len(self.files_failed)

        # Count skipped files by reason
        skipped_counts = {reason: len(files) for reason, files in self.files_skipped.items()}
        total_skipped = sum(skipped_counts.values())

        # Calculate discoverable files (non-binary, potentially parseable)
        discoverable = 0
        for file_path in self.files_discovered:
            skip_reason = self.should_skip_file(file_path)
            if skip_reason not in ["binary", "vendor_or_build_dir"]:
                discoverable += 1

        # Calculate coverage percentage
        if discoverable > 0:
            coverage_percentage = (parsed / discoverable) * 100
        else:
            coverage_percentage = 0.0

        # Check if coverage is incomplete
        is_incomplete = coverage_percentage < 80.0
        incomplete_reason = None
        if is_incomplete:
            incomplete_reason = f"Only {coverage_percentage:.1f}% of codebase scanned (minimum 80% recommended)"

        # Build parse errors list (limit to 20)
        parse_errors = [f"{file}: {error}" for file, error in self.files_failed[:20]]

        return CoverageReport(
            total_files_discovered=total_discovered,
            files_parsed_successfully=parsed,
            files_skipped=skipped_counts,
            files_failed_parsing=failed,
            coverage_percentage=coverage_percentage,
            languages_detected=dict(self.languages),
            analyzer_coverage={analyzer: analyzer in self.analyzers_run for analyzer in ["SAST", "secrets", "dependencies", "IaC"]},
            parse_errors=parse_errors,
            files_discoverable=discoverable,
            is_incomplete=is_incomplete,
            incomplete_reason=incomplete_reason,
        )

    def reset(self):
        """Reset coverage tracking."""
        self.files_discovered = []
        self.files_parsed = []
        self.files_skipped = defaultdict(list)
        self.files_failed = []
        self.languages = defaultdict(int)
        self.analyzers_run = set()

