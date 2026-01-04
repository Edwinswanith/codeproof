"""Tests for metering service."""

import pytest
from unittest.mock import MagicMock, AsyncMock


class TestUsageMetrics:
    """Test UsageMetrics dataclass."""

    def test_default_values(self):
        """UsageMetrics has zero defaults."""
        from app.services.metering_service import UsageMetrics

        metrics = UsageMetrics()

        assert metrics.embedding_tokens == 0
        assert metrics.input_tokens == 0
        assert metrics.output_tokens == 0

    def test_custom_values(self):
        """UsageMetrics accepts custom values."""
        from app.services.metering_service import UsageMetrics

        metrics = UsageMetrics(
            embedding_tokens=1000,
            input_tokens=500,
            output_tokens=200
        )

        assert metrics.embedding_tokens == 1000
        assert metrics.input_tokens == 500
        assert metrics.output_tokens == 200

    def test_estimated_cost_zero_tokens(self):
        """Zero tokens equals zero cost."""
        from app.services.metering_service import UsageMetrics

        metrics = UsageMetrics()
        cost = metrics.estimated_cost_micro_cents()

        assert cost == 0

    def test_estimated_cost_only_embeddings(self):
        """Calculates embedding cost correctly."""
        from app.services.metering_service import UsageMetrics, COSTS

        # 1000 embedding tokens
        metrics = UsageMetrics(embedding_tokens=1000)
        cost = metrics.estimated_cost_micro_cents()

        # $0.00002 per 1K tokens = $0.00002 total = 0.002 cents = 0.2 micro-cents
        expected = int(0.00002 * 10000)  # micro-cents
        assert cost == expected

    def test_estimated_cost_only_input(self):
        """Calculates input token cost correctly."""
        from app.services.metering_service import UsageMetrics, COSTS

        # 1000 input tokens
        metrics = UsageMetrics(input_tokens=1000)
        cost = metrics.estimated_cost_micro_cents()

        # $0.0025 per 1K = $0.0025 total = 0.25 cents = 25 micro-cents
        expected = int(0.0025 * 10000)
        assert cost == expected

    def test_estimated_cost_only_output(self):
        """Calculates output token cost correctly."""
        from app.services.metering_service import UsageMetrics, COSTS

        # 1000 output tokens
        metrics = UsageMetrics(output_tokens=1000)
        cost = metrics.estimated_cost_micro_cents()

        # $0.01 per 1K = $0.01 total = 1 cent = 100 micro-cents
        expected = int(0.01 * 10000)
        assert cost == expected

    def test_estimated_cost_combined(self):
        """Calculates combined cost correctly."""
        from app.services.metering_service import UsageMetrics

        metrics = UsageMetrics(
            embedding_tokens=10000,  # $0.0002
            input_tokens=5000,       # $0.0125
            output_tokens=2000       # $0.02
        )
        cost = metrics.estimated_cost_micro_cents()

        # Total: $0.0327 = 327 micro-cents
        embedding_cost = 0.00002 * 10  # 10K tokens
        input_cost = 0.0025 * 5  # 5K tokens
        output_cost = 0.01 * 2  # 2K tokens
        total = embedding_cost + input_cost + output_cost
        expected = int(total * 10000)

        assert cost == expected


class TestCosts:
    """Test cost constants."""

    def test_costs_defined(self):
        """Cost constants are defined."""
        from app.services.metering_service import COSTS

        assert "gpt-4o" in COSTS
        assert "text-embedding-3-small" in COSTS

    def test_gpt4o_costs(self):
        """GPT-4o costs are defined."""
        from app.services.metering_service import COSTS

        assert "input" in COSTS["gpt-4o"]
        assert "output" in COSTS["gpt-4o"]
        assert COSTS["gpt-4o"]["input"] > 0
        assert COSTS["gpt-4o"]["output"] > 0

    def test_embedding_costs(self):
        """Embedding costs are defined."""
        from app.services.metering_service import COSTS

        assert "input" in COSTS["text-embedding-3-small"]
        assert COSTS["text-embedding-3-small"]["input"] > 0


class TestMeteringServiceInit:
    """Test MeteringService initialization."""

    def test_init_with_db_session(self):
        """MeteringService initializes with db session."""
        from app.services.metering_service import MeteringService

        mock_db = MagicMock()
        service = MeteringService(mock_db)

        assert service.db == mock_db


class TestMeteringServiceRecordMethods:
    """Test MeteringService record methods."""

    @pytest.fixture
    def service(self):
        """Create MeteringService with mocked db."""
        from app.services.metering_service import MeteringService

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        return MeteringService(mock_db)

    @pytest.mark.asyncio
    async def test_record_indexing_creates_event(self, service):
        """record_indexing creates usage event."""
        await service.record_indexing(
            user_id="user-123",
            repo_id="repo-456",
            file_count=100,
            chunk_count=500,
            embedding_tokens=10000
        )

        # Check db.add was called
        service.db.add.assert_called_once()

        # Check commit was called
        service.db.commit.assert_called_once()

        # Get the event that was added
        event = service.db.add.call_args[0][0]
        assert event.user_id == "user-123"
        assert event.repo_id == "repo-456"
        assert event.event_type == "repo_indexed"
        assert event.embedding_tokens == 10000
        assert event.event_metadata["file_count"] == 100
        assert event.event_metadata["chunk_count"] == 500

    @pytest.mark.asyncio
    async def test_record_question_creates_event(self, service):
        """record_question creates usage event."""
        await service.record_question(
            user_id="user-123",
            repo_id="repo-456",
            input_tokens=500,
            output_tokens=200,
            embedding_tokens=1000
        )

        service.db.add.assert_called_once()
        service.db.commit.assert_called_once()

        event = service.db.add.call_args[0][0]
        assert event.event_type == "question_asked"
        assert event.input_tokens == 500
        assert event.output_tokens == 200
        assert event.embedding_tokens == 1000

    @pytest.mark.asyncio
    async def test_record_pr_review_creates_event(self, service):
        """record_pr_review creates usage event."""
        await service.record_pr_review(
            user_id="user-123",
            repo_id="repo-456",
            input_tokens=2000,
            output_tokens=500,
            files_analyzed=10
        )

        service.db.add.assert_called_once()
        service.db.commit.assert_called_once()

        event = service.db.add.call_args[0][0]
        assert event.event_type == "pr_reviewed"
        assert event.input_tokens == 2000
        assert event.output_tokens == 500
        assert event.event_metadata["files_analyzed"] == 10
