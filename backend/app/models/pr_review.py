"""PR Review model."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PRReview(Base):
    """Pull request review."""

    __tablename__ = "pr_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )

    # PR info
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pr_title: Mapped[str | None] = mapped_column(String(500))
    pr_url: Mapped[str | None] = mapped_column(String(500))
    head_sha: Mapped[str | None] = mapped_column(String(40))
    base_sha: Mapped[str | None] = mapped_column(String(40))

    # Status
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # Allowed: pending, analyzing, completed, failed

    # Stats
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, default=0)

    # GitHub integration
    review_posted: Mapped[bool] = mapped_column(Boolean, default=False)
    github_review_id: Mapped[int | None] = mapped_column(BigInteger)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
