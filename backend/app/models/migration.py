"""Migration model for Laravel migrations."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Migration(Base):
    """Laravel migration parsed for schema analysis."""

    __tablename__ = "migrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )

    # File info
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    migration_order: Mapped[int | None] = mapped_column(Integer)  # From filename timestamp

    # Table operation
    table_name: Mapped[str | None] = mapped_column(String(255))
    operation: Mapped[str | None] = mapped_column(String(20))  # create, alter, drop, rename

    # Schema details
    columns: Mapped[list] = mapped_column(JSONB, default=list)
    indexes: Mapped[list] = mapped_column(JSONB, default=list)
    foreign_keys: Mapped[list] = mapped_column(JSONB, default=list)

    # Destructive flag
    is_destructive: Mapped[bool] = mapped_column(Boolean, default=False)
    destructive_operations: Mapped[list] = mapped_column(JSONB, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
