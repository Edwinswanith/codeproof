"""PR Finding model - high-precision analyzers only."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PRFinding(Base):
    """PR finding from high-precision analyzers.

    Only 6 categories allowed (per V2 architecture):
    - secret_exposure: Exact key patterns (GitHub PAT, AWS, Stripe)
    - migration_destructive: DROP TABLE/COLUMN
    - auth_middleware_removed: ->withoutMiddleware('auth')
    - dependency_changed: Lockfile changes
    - env_leaked: .env files
    - private_key_exposed: PEM blocks
    """

    __tablename__ = "pr_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pr_review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pr_reviews.id", ondelete="CASCADE"), nullable=False
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )

    # Classification
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    # Allowed: critical, warning, info
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    # Allowed: secret_exposure, migration_destructive, auth_middleware_removed,
    #          dependency_changed, env_leaked, private_key_exposed

    # Location
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    start_line: Mapped[int | None] = mapped_column(Integer)
    end_line: Mapped[int | None] = mapped_column(Integer)

    # Evidence (REQUIRED - this makes it trustworthy)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # {
    #     "snippet": "redacted code snippet",
    #     "pattern": "GitHub Personal Access Token",
    #     "match": "ghp_xxxx...xxxx",
    #     "reason": "Token detected - this should not be in code",
    #     "confidence": "exact_match" | "structural" | "heuristic"
    # }

    # LLM explanation (generated AFTER detection, optional)
    explanation: Mapped[str | None] = mapped_column(Text)
    suggested_fix: Mapped[str | None] = mapped_column(Text)

    # GitHub state
    comment_posted: Mapped[bool] = mapped_column(Boolean, default=False)
    github_comment_id: Mapped[int | None] = mapped_column(BigInteger)

    # Resolution
    status: Mapped[str] = mapped_column(String(20), default="open")
    # Allowed: open, resolved, ignored, false_positive
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
