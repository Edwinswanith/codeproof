"""High-precision analyzer for PR reviews.

Only flags issues we're confident about.
Design principle: It's better to miss some issues than to flood
users with false positives and destroy trust.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Finding severity levels."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class Category(str, Enum):
    """Finding categories (6 high-precision only)."""

    SECRET_EXPOSURE = "secret_exposure"
    MIGRATION_DESTRUCTIVE = "migration_destructive"
    AUTH_MIDDLEWARE_REMOVED = "auth_middleware_removed"
    DEPENDENCY_CHANGED = "dependency_changed"
    ENV_LEAKED = "env_leaked"
    PRIVATE_KEY_EXPOSED = "private_key_exposed"


@dataclass
class Finding:
    """A high-precision finding."""

    severity: Severity
    category: Category
    file_path: str
    start_line: int
    end_line: int
    evidence: dict[str, Any]
    confidence: str = "exact_match"  # exact_match | structural | pattern


class HighPrecisionAnalyzer:
    """High-precision analyzer that only flags issues we're confident about."""

    # ========================================
    # EXACT MATCH PATTERNS (near 100% precision)
    # ========================================

    EXACT_PATTERNS = [
        # GitHub Personal Access Token (classic)
        {
            "pattern": r"ghp_[a-zA-Z0-9]{36}",
            "name": "GitHub Personal Access Token",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: f"ghp_{'*' * 32}...",
        },
        # GitHub Fine-grained PAT
        {
            "pattern": r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}",
            "name": "GitHub Fine-grained PAT",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: "github_pat_****...",
        },
        # AWS Access Key ID
        {
            "pattern": r"AKIA[0-9A-Z]{16}",
            "name": "AWS Access Key ID",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: f"AKIA{'*' * 12}...",
        },
        # Stripe Live Secret Key
        {
            "pattern": r"sk_live_[a-zA-Z0-9]{24,}",
            "name": "Stripe Live Secret Key",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: "sk_live_****...",
        },
        # Stripe Live Publishable Key (less critical but still flag)
        {
            "pattern": r"pk_live_[a-zA-Z0-9]{24,}",
            "name": "Stripe Live Publishable Key",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.WARNING,
            "redact": lambda m: "pk_live_****...",
        },
        # Slack Bot Token
        {
            "pattern": r"xoxb-[0-9]{11,13}-[0-9]{11,13}-[a-zA-Z0-9]{24}",
            "name": "Slack Bot Token",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: "xoxb-****...",
        },
        # Slack User Token
        {
            "pattern": r"xoxp-[0-9]{11,13}-[0-9]{11,13}-[a-zA-Z0-9]{24}",
            "name": "Slack User Token",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: "xoxp-****...",
        },
        # SendGrid API Key
        {
            "pattern": r"SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}",
            "name": "SendGrid API Key",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: "SG.****...",
        },
        # Twilio Account SID
        {
            "pattern": r"AC[a-f0-9]{32}",
            "name": "Twilio Account SID",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.WARNING,
            "redact": lambda m: "AC****...",
        },
        # RSA/EC/DSA Private Key
        {
            "pattern": r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
            "name": "Private Key",
            "category": Category.PRIVATE_KEY_EXPOSED,
            "severity": Severity.CRITICAL,
            "redact": lambda m: "-----BEGIN PRIVATE KEY-----",
        },
    ]

    # ========================================
    # FILE-BASED PATTERNS
    # ========================================

    DANGEROUS_FILES = [
        {
            "pattern": r"^\.env$",
            "name": ".env file committed",
            "category": Category.ENV_LEAKED,
            "severity": Severity.CRITICAL,
        },
        {
            "pattern": r"^\.env\.(local|production|staging)$",
            "name": "Environment file committed",
            "category": Category.ENV_LEAKED,
            "severity": Severity.CRITICAL,
        },
        {
            "pattern": r"id_rsa$|id_ed25519$|id_ecdsa$",
            "name": "SSH private key committed",
            "category": Category.PRIVATE_KEY_EXPOSED,
            "severity": Severity.CRITICAL,
        },
    ]

    LOCKFILES = [
        "composer.lock",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Gemfile.lock",
        "poetry.lock",
    ]

    # ========================================
    # MIGRATION PATTERNS (Laravel)
    # ========================================

    DESTRUCTIVE_MIGRATION_PATTERNS = [
        {
            "pattern": r"Schema::drop(?:IfExists)?\s*\(\s*['\"](\w+)['\"]",
            "name": "DROP TABLE",
            "extract_target": 1,  # Group 1 contains table name
        },
        {
            "pattern": r"\$table->dropColumn\s*\(\s*['\"](\w+)['\"]",
            "name": "DROP COLUMN",
            "extract_target": 1,
        },
        {
            "pattern": r"\$table->dropColumn\s*\(\s*\[([^\]]+)\]",
            "name": "DROP COLUMNS",
            "extract_target": 1,
        },
        {
            "pattern": r"Schema::rename\s*\(",
            "name": "RENAME TABLE",
            "extract_target": None,
        },
        {
            "pattern": r"\$table->renameColumn\s*\(",
            "name": "RENAME COLUMN",
            "extract_target": None,
        },
    ]

    # ========================================
    # AUTH PATTERNS (Laravel)
    # ========================================

    AUTH_MIDDLEWARE_REMOVAL_PATTERN = re.compile(
        r"->withoutMiddleware\s*\(\s*['\"](auth|verified|can|admin)['\"]",
        re.IGNORECASE,
    )

    def __init__(self):
        # Compile patterns
        self.compiled_exact = [
            {**p, "compiled": re.compile(p["pattern"])} for p in self.EXACT_PATTERNS
        ]
        self.compiled_files = [
            {**p, "compiled": re.compile(p["pattern"])} for p in self.DANGEROUS_FILES
        ]
        self.compiled_migrations = [
            {**p, "compiled": re.compile(p["pattern"], re.IGNORECASE)}
            for p in self.DESTRUCTIVE_MIGRATION_PATTERNS
        ]

    def analyze_file(
        self,
        file_path: str,
        content: str,
        diff_lines: list[int] | None = None,
    ) -> list[Finding]:
        """Analyze a single file for high-precision issues.

        Args:
            file_path: File path
            content: File content
            diff_lines: Optional list of line numbers in diff

        Returns:
            List of findings
        """
        findings = []

        # Check dangerous file patterns
        findings.extend(self._check_dangerous_file(file_path))

        # Check lockfile changes
        if self._is_lockfile(file_path):
            findings.append(
                Finding(
                    severity=Severity.INFO,
                    category=Category.DEPENDENCY_CHANGED,
                    file_path=file_path,
                    start_line=1,
                    end_line=1,
                    evidence={
                        "snippet": f"{file_path} was modified",
                        "reason": "Dependency lockfile changed - review for security implications",
                        "confidence": "exact_match",
                    },
                )
            )

        # Check content patterns
        if content:
            findings.extend(self._check_exact_patterns(file_path, content, diff_lines))

            if self._is_migration_file(file_path):
                findings.extend(
                    self._check_destructive_migrations(file_path, content, diff_lines)
                )

            if self._is_route_file(file_path):
                findings.extend(
                    self._check_auth_middleware_removal(file_path, content, diff_lines)
                )

        return findings

    def _check_dangerous_file(self, file_path: str) -> list[Finding]:
        """Check if file itself is dangerous to commit."""
        findings = []
        filename = file_path.split("/")[-1]

        for pattern in self.compiled_files:
            if pattern["compiled"].search(filename):
                findings.append(
                    Finding(
                        severity=pattern["severity"],
                        category=pattern["category"],
                        file_path=file_path,
                        start_line=1,
                        end_line=1,
                        evidence={
                            "snippet": file_path,
                            "pattern": pattern["pattern"],
                            "reason": f"{pattern['name']} - this file should not be committed",
                            "confidence": "exact_match",
                        },
                    )
                )

        return findings

    def _is_lockfile(self, file_path: str) -> bool:
        """Check if file is a dependency lockfile."""
        filename = file_path.split("/")[-1]
        return filename in self.LOCKFILES

    def _is_migration_file(self, file_path: str) -> bool:
        """Check if file is a Laravel migration."""
        return "migrations/" in file_path.lower() and file_path.endswith(".php")

    def _is_route_file(self, file_path: str) -> bool:
        """Check if file is a Laravel route file."""
        return "routes/" in file_path.lower() and file_path.endswith(".php")

    def _check_exact_patterns(
        self,
        file_path: str,
        content: str,
        diff_lines: list[int] | None,
    ) -> list[Finding]:
        """Check for exact-match secret patterns."""
        findings = []

        # Skip files that are unlikely to contain real secrets
        if self._should_skip_file(file_path):
            return findings

        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Skip if not in diff (when diff_lines provided)
            if diff_lines and line_num not in diff_lines:
                continue

            for pattern in self.compiled_exact:
                match = pattern["compiled"].search(line)
                if match:
                    # Redact the match for safe display
                    redacted = pattern["redact"](match)

                    findings.append(
                        Finding(
                            severity=pattern["severity"],
                            category=pattern["category"],
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            evidence={
                                "snippet": self._redact_line(line, match),
                                "pattern": pattern["name"],
                                "match": redacted,
                                "reason": f"{pattern['name']} detected - this should not be in code",
                                "confidence": "exact_match",
                            },
                        )
                    )

        return findings

    def _check_destructive_migrations(
        self,
        file_path: str,
        content: str,
        diff_lines: list[int] | None,
    ) -> list[Finding]:
        """Check for destructive migration operations."""
        findings = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            if diff_lines and line_num not in diff_lines:
                continue

            for pattern in self.compiled_migrations:
                match = pattern["compiled"].search(line)
                if match:
                    target = ""
                    if pattern["extract_target"] is not None:
                        try:
                            target = match.group(pattern["extract_target"])
                        except IndexError:
                            pass

                    reason = f"{pattern['name']}"
                    if target:
                        reason += f" on '{target}'"
                    reason += " - this will cause data loss"

                    findings.append(
                        Finding(
                            severity=Severity.CRITICAL,
                            category=Category.MIGRATION_DESTRUCTIVE,
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            evidence={
                                "snippet": line.strip(),
                                "operation": pattern["name"],
                                "target": target,
                                "reason": reason,
                                "confidence": "exact_match",
                            },
                        )
                    )

        return findings

    def _check_auth_middleware_removal(
        self,
        file_path: str,
        content: str,
        diff_lines: list[int] | None,
    ) -> list[Finding]:
        """Check for auth middleware being removed from routes."""
        findings = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            if diff_lines and line_num not in diff_lines:
                continue

            match = self.AUTH_MIDDLEWARE_REMOVAL_PATTERN.search(line)
            if match:
                middleware = match.group(1)
                findings.append(
                    Finding(
                        severity=Severity.CRITICAL,
                        category=Category.AUTH_MIDDLEWARE_REMOVED,
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence={
                            "snippet": line.strip(),
                            "middleware": middleware,
                            "reason": f"'{middleware}' middleware is being removed - this may expose the route to unauthorized access",
                            "confidence": "structural",
                        },
                    )
                )

        return findings

    def _should_skip_file(self, file_path: str) -> bool:
        """Check if file should be skipped for secret scanning."""
        skip_patterns = [
            ".lock",
            ".min.js",
            ".min.css",
            ".map",
            ".svg",
            ".png",
            ".jpg",
            ".gif",
            ".ico",
            ".woff",
            ".ttf",
            "/vendor/",
            "/node_modules/",
            "/dist/",
            "/build/",
            "__pycache__",
        ]

        path_lower = file_path.lower()
        return any(pattern in path_lower for pattern in skip_patterns)

    def _redact_line(self, line: str, match: re.Match) -> str:
        """Redact the matched secret in the line."""
        start, end = match.span()
        secret = match.group()

        # Show first 4 and last 4 chars
        if len(secret) > 12:
            redacted = secret[:4] + "*" * (len(secret) - 8) + secret[-4:]
        else:
            redacted = secret[:2] + "*" * (len(secret) - 2)

        return line[:start] + redacted + line[end:]

