from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Import(Base):
    __tablename__ = "imports"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed')", name="ck_imports_status"),
        CheckConstraint("input_type IN ('text', 'url', 'file')", name="ck_imports_input_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    extracted_menu: Mapped[ExtractedMenu | None] = relationship(
        back_populates="import_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    events: Mapped[list[ImportEvent]] = relationship(
        back_populates="import_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ImportEvent.created_at",
    )


class ExtractedMenu(Base):
    __tablename__ = "extracted_menus"
    __table_args__ = (
        CheckConstraint(
            "validation_status IN ('pending', 'valid', 'invalid')",
            name="ck_extracted_menus_validation_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("imports.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    canonical_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    restaurant_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    import_record: Mapped[Import] = relationship(back_populates="extracted_menu")


class ImportEvent(Base):
    __tablename__ = "import_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    import_record: Mapped[Import] = relationship(back_populates="events")


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = (
        CheckConstraint("case_set IN ('required', 'additional')", name="ck_evaluation_cases_case_set"),
        UniqueConstraint("slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    case_set: Mapped[str] = mapped_column(String(32), nullable=False)
    source_fixture_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_fixture_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actual_fixture_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qualitative_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    weaknesses: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_set: Mapped[str] = mapped_column(String(32), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
