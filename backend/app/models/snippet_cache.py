"""Snippet cache model - temporary, auto-expire."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def default_expiry() -> datetime:
    """Default expiry time (1 hour from now)."""
    return datetime.utcnow() + timedelta(hours=1)


class SnippetCache(Base):
    """Cached code snippets fetched from GitHub.

    Per V2 architecture:
    - Snippets are fetched fresh from GitHub API
    - Cached for 1 hour maximum
    - Cleanup job: DELETE FROM snippet_cache WHERE expires_at < NOW()
    """

    __tablename__ = "snippet_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )

    # Location
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, default=default_expiry)

    __table_args__ = (
        UniqueConstraint(
            "repo_id",
            "commit_sha",
            "file_path",
            "start_line",
            "end_line",
            name="uq_snippet_cache_location",
        ),
    )
