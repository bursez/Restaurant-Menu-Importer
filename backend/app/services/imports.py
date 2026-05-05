from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExtractedMenu, Import, ImportEvent
from app.domain.imports import ImportInputType, ImportStatus, ValidationStatus
from app.repositories.imports import ImportRepository


class ImportNotFoundError(Exception):
    pass


class ImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ImportRepository(session)

    async def create_import(
        self,
        *,
        input_type: ImportInputType,
        source_value: str | None = None,
        source_filename: str | None = None,
        status: ImportStatus = ImportStatus.PENDING,
    ) -> Import:
        import_record = await self.repository.create_import(
            input_type=input_type,
            source_value=source_value,
            source_filename=source_filename,
            status=status,
        )
        await self.repository.add_event(
            import_record,
            stage="created",
            message=f"{input_type.value} import created",
        )
        await self.session.commit()
        await self.session.refresh(import_record)
        return import_record

    async def list_imports(self, *, limit: int = 50, offset: int = 0) -> Sequence[Import]:
        return await self.repository.list_imports(limit=limit, offset=offset)

    async def get_import(self, import_id: uuid.UUID) -> Import:
        import_record = await self.repository.get_import(import_id, include_children=True)
        if import_record is None:
            raise ImportNotFoundError
        return import_record

    async def update_status(
        self,
        import_id: uuid.UUID,
        *,
        status: ImportStatus,
        error_message: str | None = None,
        model_used: str | None = None,
        duration_ms: int | None = None,
    ) -> Import:
        import_record = await self.get_import(import_id)
        await self.repository.update_import_status(
            import_record,
            status=status,
            error_message=error_message,
            model_used=model_used,
            duration_ms=duration_ms,
        )
        await self.repository.add_event(
            import_record,
            stage="status",
            message=f"Import marked {status.value}",
            event_metadata={"status": status.value},
        )
        await self.session.commit()
        await self.session.refresh(import_record)
        return import_record

    async def record_event(
        self,
        import_id: uuid.UUID,
        *,
        stage: str,
        message: str,
        event_metadata: dict[str, Any] | None = None,
    ) -> ImportEvent:
        import_record = await self.get_import(import_id)
        event = await self.repository.add_event(
            import_record,
            stage=stage,
            message=message,
            event_metadata=event_metadata,
        )
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def save_extracted_menu(
        self,
        import_id: uuid.UUID,
        *,
        canonical_json: dict[str, Any],
        validation_status: ValidationStatus,
        restaurant_name: str | None = None,
        currency: str | None = None,
        language: str | None = None,
        confidence_score: Decimal | None = None,
    ) -> ExtractedMenu:
        import_record = await self.get_import(import_id)
        extracted_menu = await self.repository.upsert_extracted_menu(
            import_record,
            canonical_json=canonical_json,
            validation_status=validation_status,
            restaurant_name=restaurant_name,
            currency=currency,
            language=language,
            confidence_score=confidence_score,
        )
        await self.repository.add_event(
            import_record,
            stage="validation",
            message=f"Extracted menu saved as {validation_status.value}",
            event_metadata={"validation_status": validation_status.value},
        )
        await self.session.commit()
        await self.session.refresh(extracted_menu)
        return extracted_menu
