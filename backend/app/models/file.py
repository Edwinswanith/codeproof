"""File model - metadata only, NO content storage."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class File(Base):
    """File metadata model - NO content column per V2 architecture."""

    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )

    # File metadata
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha: Mapped[str] = mapped_column(String(40), nullable=False)  # Git blob SHA
    language: Mapped[str | None] = mapped_column(String(50))
    size_bytes: Mapped[int | None] = mapped_column(Integer)

    # Timestamps
    last_indexed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        # Unique constraint on repo + path
        {"sqlite_autoincrement": True},
    )
