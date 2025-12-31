"""Answer model for Q&A with structured validation."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Answer(Base):
    """Q&A answer with proof-carrying validation."""

    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Question
    question: Mapped[str] = mapped_column(Text, nullable=False)

    # Structured answer
    answer_text: Mapped[str | None] = mapped_column(Text)
    answer_sections: Mapped[list | None] = mapped_column(JSONB)  # [{text, source_ids}]
    unknowns: Mapped[list] = mapped_column(JSONB, default=list)

    # Confidence (discrete tier, not percentage)
    confidence_tier: Mapped[str | None] = mapped_column(String(10))  # high, medium, low, none
    confidence_factors: Mapped[dict | None] = mapped_column(JSONB)

    # Validation
    validation_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_errors: Mapped[list] = mapped_column(JSONB, default=list)

    # Metadata
    retrieval_stats: Mapped[dict | None] = mapped_column(JSONB)
    llm_model: Mapped[str | None] = mapped_column(String(50))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)

    # Feedback
    feedback: Mapped[str | None] = mapped_column(String(10))  # up, down
    feedback_comment: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
