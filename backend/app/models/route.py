"""Route model for Laravel routes extracted via AST."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Route(Base):
    """Laravel route extracted via AST-based parsing."""

    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )

    # Route definition
    method: Mapped[str] = mapped_column(String(10), nullable=False)  # GET, POST, etc.
    uri: Mapped[str] = mapped_column(String(500), nullable=False)
    full_uri: Mapped[str] = mapped_column(String(500), nullable=False)  # With prefix
    name: Mapped[str | None] = mapped_column(String(255))

    # Handler
    controller: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str | None] = mapped_column(String(255))
    handler_type: Mapped[str | None] = mapped_column(String(20))  # controller, closure, invokable

    # Middleware chain (in order)
    middleware: Mapped[list] = mapped_column(JSONB, default=list)

    # Group context
    group_prefix: Mapped[str | None] = mapped_column(String(255))
    group_middleware: Mapped[list] = mapped_column(JSONB, default=list)

    # Source location
    source_file: Mapped[str] = mapped_column(String(1000), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int | None] = mapped_column(Integer)

    # Linked entities
    controller_symbol_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("symbols.id")
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
