from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ExtractedMenu, Import, ImportEvent
from app.domain.imports import ImportInputType, ImportStatus, ValidationStatus


class ImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_import(
        self,
        *,
        input_type: ImportInputType,
        source_value: str | None = None,
        source_filename: str | None = None,
        status: ImportStatus = ImportStatus.PENDING,
    ) -> Import:
        import_record = Import(
            input_type=input_type.value,
            source_value=source_value,
            source_filename=source_filename,
            status=status.value,
        )
        self.session.add(import_record)
        await self.session.flush()
        return import_record

    async def get_import(self, import_id: uuid.UUID, *, include_children: bool = False) -> Import | None:
        statement: Select[tuple[Import]] = select(Import).where(Import.id == import_id)
        if include_children:
            statement = statement.options(selectinload(Import.events), selectinload(Import.extracted_menu))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_imports(self, *, limit: int = 50, offset: int = 0) -> Sequence[Import]:
        statement = (
            select(Import)
            .options(selectinload(Import.extracted_menu))
            .order_by(Import.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def update_import_status(
        self,
        import_record: Import,
        *,
        status: ImportStatus,
        error_message: str | None = None,
        model_used: str | None = None,
        duration_ms: int | None = None,
    ) -> Import:
        import_record.status = status.value
        import_record.error_message = error_message
        if model_used is not None:
            import_record.model_used = model_used
        if duration_ms is not None:
            import_record.duration_ms = duration_ms
        await self.session.flush()
        return import_record

    async def add_event(
        self,
        import_record: Import,
        *,
        stage: str,
        message: str,
        event_metadata: dict[str, Any] | None = None,
    ) -> ImportEvent:
        event = ImportEvent(
            import_record=import_record,
            stage=stage,
            message=message,
            event_metadata=event_metadata or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def upsert_extracted_menu(
        self,
        import_record: Import,
        *,
        canonical_json: dict[str, Any],
        validation_status: ValidationStatus,
        restaurant_name: str | None = None,
        currency: str | None = None,
        language: str | None = None,
        confidence_score: Decimal | None = None,
    ) -> ExtractedMenu:
        if import_record.extracted_menu is None:
            extracted_menu = ExtractedMenu(import_id=import_record.id, canonical_json=canonical_json)
            import_record.extracted_menu = extracted_menu
            self.session.add(extracted_menu)
        else:
            extracted_menu = import_record.extracted_menu
            extracted_menu.canonical_json = canonical_json

        extracted_menu.validation_status = validation_status.value
        extracted_menu.restaurant_name = restaurant_name
        extracted_menu.currency = currency
        extracted_menu.language = language
        extracted_menu.confidence_score = confidence_score
        await self.session.flush()
        return extracted_menu
