"""Repository model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Repository(Base):
    """Repository model - metadata only, no file content."""

    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # GitHub identifiers
    github_repo_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    github_installation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    private: Mapped[bool] = mapped_column(Boolean, default=True)

    # Framework detection
    detected_framework: Mapped[str] = mapped_column(String(50), default="laravel")
    framework_version: Mapped[str | None] = mapped_column(String(20))

    # Index status
    index_status: Mapped[str] = mapped_column(String(20), default="pending")
    index_error: Mapped[str | None] = mapped_column(Text)
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_indexed_commit: Mapped[str | None] = mapped_column(String(40))

    # Stats
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    symbol_count: Mapped[int] = mapped_column(Integer, default=0)
    route_count: Mapped[int] = mapped_column(Integer, default=0)

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="repositories")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def is_ready(self) -> bool:
        return self.index_status == "ready"
