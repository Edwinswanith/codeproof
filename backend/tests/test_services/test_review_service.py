"""Tests for PR review service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestReviewServiceDiffParsing:
    """Test diff parsing utilities."""

    @pytest.fixture
    def service(self):
        """Create ReviewService with mocked dependencies."""
        from app.services.review_service import ReviewService

        mock_db = MagicMock()
        mock_github = MagicMock()
        mock_llm = MagicMock()

        return ReviewService(mock_db, mock_github, mock_llm)

    def test_parse_simple_diff(self, service):
        """Parses simple diff with added lines."""
        patch = """@@ -0,0 +1,3 @@
+line 1
+line 2
+line 3"""

        lines = service._parse_diff_lines(patch)
        assert lines == [1, 2, 3]

    def test_parse_diff_with_context(self, service):
        """Parses diff with context lines."""
        patch = """@@ -10,5 +10,7 @@
 context line
+added line 1
 more context
+added line 2
 final context"""

        lines = service._parse_diff_lines(patch)
        # Line 11 and 13 are added
        assert 11 in lines
        assert 13 in lines

    def test_parse_empty_patch(self, service):
        """Returns empty list for empty patch."""
        lines = service._parse_diff_lines("")
        assert lines == []

    def test_parse_none_patch(self, service):
        """Returns empty list for None patch."""
        lines = service._parse_diff_lines(None)
        assert lines == []

    def test_parse_multiple_hunks(self, service):
        """Parses diff with multiple hunks."""
        patch = """@@ -1,3 +1,4 @@
 line 1
+new line 2
 line 3
 line 4
@@ -10,2 +11,3 @@
 line 10
+new line 11
 line 12"""

        lines = service._parse_diff_lines(patch)
        # Added lines: 2 (in first hunk), 12 (in second hunk)
        assert 2 in lines
        assert 12 in lines

    def test_parse_deleted_lines_ignored(self, service):
        """Deleted lines are not included."""
        patch = """@@ -1,4 +1,2 @@
-deleted line 1
 kept line
-deleted line 2
+added line"""

        lines = service._parse_diff_lines(patch)
        # Only added line should be returned
        assert len(lines) == 1

    def test_parse_real_diff(self, service):
        """Parses realistic diff output."""
        patch = """@@ -15,6 +15,9 @@ class Config:
     secret_key: str
     jwt_secret: str

+    # New config option
+    api_key: str = "default"
+
     @field_validator("secret_key")
     @classmethod
     def validate_secret(cls, v):"""

        lines = service._parse_diff_lines(patch)
        # Lines 18, 19, 20 are added
        assert 18 in lines
        assert 19 in lines
        assert 20 in lines


class TestReviewServiceBuildComment:
    """Test comment building logic."""

    @pytest.fixture
    def service(self):
        """Create ReviewService with mocked dependencies."""
        from app.services.review_service import ReviewService

        mock_db = MagicMock()
        mock_github = MagicMock()
        mock_llm = MagicMock()

        svc = ReviewService(mock_db, mock_github, mock_llm)

        # Initialize analyzer lazily
        from app.analyzers.high_precision_analyzer import HighPrecisionAnalyzer, Finding, Severity
        svc.analyzer = HighPrecisionAnalyzer()
        svc.Finding = Finding
        svc.Severity = Severity

        return svc

    def test_analyzer_initialized(self, service):
        """Analyzer is properly initialized."""
        assert service.analyzer is not None
        assert service.Severity is not None


class TestReviewServiceAnalysis:
    """Test file analysis integration."""

    @pytest.fixture
    def service(self):
        """Create ReviewService with mocked dependencies."""
        from app.services.review_service import ReviewService
        from app.analyzers.high_precision_analyzer import HighPrecisionAnalyzer, Finding, Severity

        mock_db = MagicMock()
        mock_github = MagicMock()
        mock_llm = MagicMock()

        svc = ReviewService(mock_db, mock_github, mock_llm)
        svc.analyzer = HighPrecisionAnalyzer()
        svc.Finding = Finding
        svc.Severity = Severity

        return svc

    def test_analyze_file_with_secret(self, service):
        """Analyzer detects secrets through service."""
        content = "API_KEY = 'ghp_1234567890abcdefghijklmnopqrstuvwxyz'"
        findings = service.analyzer.analyze_file("config.py", content)

        assert len(findings) == 1
        assert findings[0].severity == service.Severity.CRITICAL

    def test_analyze_migration_file(self, service):
        """Analyzer detects destructive migration through service."""
        content = "Schema::drop('users');"
        findings = service.analyzer.analyze_file(
            "database/migrations/2024_drop_users.php",
            content
        )

        assert len(findings) == 1
        assert "DROP TABLE" in findings[0].evidence["operation"]

    def test_analyze_file_with_diff_lines(self, service):
        """Analyzer respects diff_lines filter."""
        content = """line 1
ghp_1234567890abcdefghijklmnopqrstuvwxyz on line 2
line 3
AKIAIOSFODNN7EXAMPLE on line 4
"""
        # Only check line 4
        findings = service.analyzer.analyze_file("config.py", content, diff_lines=[4])

        assert len(findings) == 1
        assert "AWS Access Key ID" in findings[0].evidence["pattern"]


class TestReviewServiceIntegration:
    """Integration tests with mocked external services."""

    @pytest.fixture
    def service(self):
        """Create ReviewService with mocked async dependencies."""
        from app.services.review_service import ReviewService
        from app.analyzers.high_precision_analyzer import HighPrecisionAnalyzer, Finding, Severity

        mock_db = MagicMock()
        mock_github = AsyncMock()
        mock_llm = AsyncMock()

        svc = ReviewService(mock_db, mock_github, mock_llm)
        svc.analyzer = HighPrecisionAnalyzer()
        svc.Finding = Finding
        svc.Severity = Severity

        return svc

    @pytest.mark.asyncio
    async def test_add_explanations_calls_llm(self, service):
        """_add_explanations calls LLM service."""
        from app.analyzers.high_precision_analyzer import Finding, Severity, Category

        service.llm_service.generate = AsyncMock(return_value="This is an explanation.")

        findings = [
            Finding(
                severity=Severity.CRITICAL,
                category=Category.SECRET_EXPOSURE,
                file_path="config.py",
                start_line=1,
                end_line=1,
                evidence={
                    "reason": "GitHub token exposed",
                    "snippet": "token = 'ghp_xxx'"
                }
            )
        ]

        await service._add_explanations(findings)

        # Check LLM was called
        service.llm_service.generate.assert_called_once()

        # Check explanation was added
        assert findings[0].evidence.get("explanation") == "This is an explanation."

    @pytest.mark.asyncio
    async def test_add_explanations_limits_to_five(self, service):
        """_add_explanations only processes first 5 findings."""
        from app.analyzers.high_precision_analyzer import Finding, Severity, Category

        service.llm_service.generate = AsyncMock(return_value="Explanation")

        # Create 10 findings
        findings = [
            Finding(
                severity=Severity.CRITICAL,
                category=Category.SECRET_EXPOSURE,
                file_path=f"file{i}.py",
                start_line=1,
                end_line=1,
                evidence={"reason": f"Finding {i}", "snippet": "code"}
            )
            for i in range(10)
        ]

        await service._add_explanations(findings)

        # Should only call LLM 5 times
        assert service.llm_service.generate.call_count == 5
