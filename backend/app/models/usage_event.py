"""Usage event model for metering."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UsageEvent(Base):
    """Usage event for metering and cost tracking.

    Event types:
    - repo_indexed: Full repo indexing
    - question_asked: Q&A operation
    - pr_reviewed: PR review operation
    - snippet_fetched: Individual snippet fetch
    """

    __tablename__ = "usage_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    repo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="SET NULL")
    )

    # Event type
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Token tracking
    embedding_tokens: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Cost in micro-cents (hundredths of a cent)
    estimated_cost_micro_cents: Mapped[int] = mapped_column(Integer, default=0)

    # Additional metadata
    event_metadata: Mapped[dict] = mapped_column(JSONB, name="metadata", default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
