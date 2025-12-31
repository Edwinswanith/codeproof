"""Symbol model for code entities extracted via tree-sitter."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Symbol(Base):
    """Code symbol extracted via tree-sitter AST parsing."""

    __tablename__ = "symbols"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )

    # Symbol identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    qualified_name: Mapped[str | None] = mapped_column(String(500))
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    # Allowed kinds: class, trait, interface, function, method, constant

    # Location
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)

    # Code details
    signature: Mapped[str | None] = mapped_column(Text)
    docstring: Mapped[str | None] = mapped_column(Text)

    # Hierarchy
    parent_symbol_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("symbols.id")
    )
    visibility: Mapped[str | None] = mapped_column(String(20))  # public, protected, private
    is_static: Mapped[bool] = mapped_column(Boolean, default=False)

    # Searchable text (name + signature + docstring combined)
    search_text: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
