"""Citation model for answer source references."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Citation(Base):
    """Citation linking answer to source code."""

    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    answer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("answers.id", ondelete="CASCADE"), nullable=False
    )

    # Source index (the [Source N] number)
    source_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Location
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)

    # Snippet (max 500 chars, fetched from GitHub)
    snippet: Mapped[str] = mapped_column(String(500), nullable=False)
    snippet_sha: Mapped[str | None] = mapped_column(String(40))

    # Symbol reference
    symbol_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("symbols.id")
    )
    symbol_name: Mapped[str | None] = mapped_column(String(255))

    # Retrieval info
    relevance_score: Mapped[float | None] = mapped_column(Float)
    retrieval_source: Mapped[str | None] = mapped_column(String(20))  # trigram, vector, both

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "answer_id", "file_path", "start_line", "end_line", name="uq_citations_answer_location"
        ),
    )
