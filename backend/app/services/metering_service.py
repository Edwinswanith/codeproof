"""Metering service for usage tracking and cost calculation."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_event import UsageEvent

# Cost per 1K tokens (as of Dec 2024)
COSTS = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},  # $2.50/$10 per 1M
    "text-embedding-3-small": {"input": 0.00002},  # $0.02 per 1M
}


@dataclass
class UsageMetrics:
    """Usage metrics for cost calculation."""

    embedding_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def estimated_cost_micro_cents(self) -> int:
        """Calculate cost in micro-cents (hundredths of a cent).

        Returns:
            Cost in micro-cents
        """
        embedding_cost = (self.embedding_tokens / 1000) * COSTS["text-embedding-3-small"]["input"]
        input_cost = (self.input_tokens / 1000) * COSTS["gpt-4o"]["input"]
        output_cost = (self.output_tokens / 1000) * COSTS["gpt-4o"]["output"]

        total_dollars = embedding_cost + input_cost + output_cost
        return int(total_dollars * 10000)  # Convert to micro-cents for precision


class MeteringService:
    """Service for tracking usage and costs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_indexing(
        self,
        user_id: str,
        repo_id: str,
        file_count: int,
        chunk_count: int,
        embedding_tokens: int,
    ) -> None:
        """Record indexing usage.

        Args:
            user_id: User UUID
            repo_id: Repository UUID
            file_count: Number of files indexed
            chunk_count: Number of chunks created
            embedding_tokens: Total embedding tokens used
        """
        metrics = UsageMetrics(embedding_tokens=embedding_tokens)

        await self._record_event(
            user_id=user_id,
            repo_id=repo_id,
            event_type="repo_indexed",
            metrics=metrics,
            metadata={
                "file_count": file_count,
                "chunk_count": chunk_count,
            },
        )

    async def record_question(
        self,
        user_id: str,
        repo_id: str,
        input_tokens: int,
        output_tokens: int,
        embedding_tokens: int,
    ) -> None:
        """Record Q&A usage.

        Args:
            user_id: User UUID
            repo_id: Repository UUID
            input_tokens: LLM input tokens
            output_tokens: LLM output tokens
            embedding_tokens: Embedding tokens used
        """
        metrics = UsageMetrics(
            embedding_tokens=embedding_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        await self._record_event(
            user_id=user_id,
            repo_id=repo_id,
            event_type="question_asked",
            metrics=metrics,
        )

    async def record_pr_review(
        self,
        user_id: str,
        repo_id: str,
        input_tokens: int,
        output_tokens: int,
        files_analyzed: int,
    ) -> None:
        """Record PR review usage.

        Args:
            user_id: User UUID
            repo_id: Repository UUID
            input_tokens: LLM input tokens
            output_tokens: LLM output tokens
            files_analyzed: Number of files analyzed
        """
        metrics = UsageMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        await self._record_event(
            user_id=user_id,
            repo_id=repo_id,
            event_type="pr_reviewed",
            metrics=metrics,
            metadata={"files_analyzed": files_analyzed},
        )

    async def _record_event(
        self,
        user_id: str,
        repo_id: str | None,
        event_type: str,
        metrics: UsageMetrics,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a usage event.

        Args:
            user_id: User UUID
            repo_id: Repository UUID (optional)
            event_type: Event type
            metrics: Usage metrics
            metadata: Additional metadata
        """
        event = UsageEvent(
            user_id=user_id,
            repo_id=repo_id,
            event_type=event_type,
            embedding_tokens=metrics.embedding_tokens,
            input_tokens=metrics.input_tokens,
            output_tokens=metrics.output_tokens,
            estimated_cost_micro_cents=metrics.estimated_cost_micro_cents(),
            event_metadata=metadata or {},
        )
        self.db.add(event)
        await self.db.commit()

    async def get_user_costs(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Get user's usage and costs for a period.

        Args:
            user_id: User UUID
            start_date: Start date (optional)
            end_date: End date (optional)

        Returns:
            Dictionary with usage stats and costs
        """
        query = select(
            UsageEvent.event_type,
            func.count().label("count"),
            func.sum(UsageEvent.embedding_tokens).label("total_embedding_tokens"),
            func.sum(UsageEvent.input_tokens).label("total_input_tokens"),
            func.sum(UsageEvent.output_tokens).label("total_output_tokens"),
            func.sum(UsageEvent.estimated_cost_micro_cents).label("total_cost_micro_cents"),
        ).where(UsageEvent.user_id == user_id)

        if start_date:
            query = query.where(UsageEvent.created_at >= start_date)
        if end_date:
            query = query.where(UsageEvent.created_at <= end_date)

        query = query.group_by(UsageEvent.event_type)

        result = await self.db.execute(query)
        rows = result.all()

        costs: dict[str, Any] = {}
        total_micro_cents = 0

        for row in rows:
            costs[row.event_type] = {
                "count": row.count,
                "embedding_tokens": row.total_embedding_tokens or 0,
                "input_tokens": row.total_input_tokens or 0,
                "output_tokens": row.total_output_tokens or 0,
                "cost_cents": (row.total_cost_micro_cents or 0) / 100,
            }
            total_micro_cents += row.total_cost_micro_cents or 0

        costs["total_cost_cents"] = total_micro_cents / 100
        costs["total_cost_dollars"] = total_micro_cents / 10000

        return costs

