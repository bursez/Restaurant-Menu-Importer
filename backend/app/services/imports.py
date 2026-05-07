from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import sanitize_error_message
from app.db.models import ExtractedMenu, Import, ImportEvent
from app.domain.imports import ImportInputType, ImportStatus, ValidationStatus
from app.repositories.imports import ImportRepository
from app.services.fake_gemini import FakeGeminiAdapter
from app.services.gemini_client import HttpGeminiAdapter
from app.services.html_extraction import discover_pdf_links, extract_html_text
from app.services.menu_extraction import MenuExtractionError, MenuExtractionService
from app.services.menu_validation import validate_canonical_menu
from app.services.pdf_extraction import extract_pdf_text
from app.services.text_imports import normalize_import_text
from app.services.url_fetching import fetch_url, is_html_response, is_pdf_response


class UrlImportError(ValueError):
    pass


class ImportNotFoundError(Exception):
    pass


class ExtractedMenuNotFoundError(Exception):
    pass


class ImportService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        menu_extraction_service: MenuExtractionService | None = None,
    ) -> None:
        self.session = session
        self.repository = ImportRepository(session)
        self.menu_extraction_service = menu_extraction_service or _build_menu_extraction_service()

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
        return await self.get_import(import_record.id)

    async def list_imports(self, *, limit: int = 50, offset: int = 0) -> Sequence[Import]:
        return await self.repository.list_imports(limit=limit, offset=offset)

    async def create_text_import(
        self,
        *,
        text: str,
        source_name: str | None = None,
    ) -> Import:
        normalized_text = normalize_import_text(text)
        import_record = await self.repository.create_import(
            input_type=ImportInputType.TEXT,
            source_value=normalized_text,
            source_filename=source_name,
            status=ImportStatus.PENDING,
        )
        await self.repository.add_event(
            import_record,
            stage="created",
            message="Text import created",
            event_metadata={
                "character_count": len(normalized_text),
                "line_count": normalized_text.count("\n") + 1,
            },
        )
        await self.session.commit()
        return await self._extract_import(import_record.id)

    async def create_file_import(
        self,
        *,
        text: str,
        filename: str,
    ) -> Import:
        normalized_text = normalize_import_text(text)
        import_record = await self.repository.create_import(
            input_type=ImportInputType.FILE,
            source_value=normalized_text,
            source_filename=filename,
            status=ImportStatus.PENDING,
        )
        await self.repository.add_event(
            import_record,
            stage="created",
            message="File import created",
            event_metadata={
                "character_count": len(normalized_text),
                "line_count": normalized_text.count("\n") + 1,
                "filename": filename,
            },
        )
        await self.session.commit()
        return await self._extract_import(import_record.id)

    async def create_url_import(self, *, url: str) -> Import:
        fetched_url = await fetch_url(url)

        pdf_links: list[str] = []
        extract_message: str
        extract_metadata: dict[str, Any]
        if is_html_response(fetched_url):
            extraction = extract_html_text(fetched_url.content)
            source_text = extraction.text
            pdf_links = discover_pdf_links(fetched_url.content, base_url=fetched_url.final_url)
            extract_message = "HTML menu text extracted"
            extract_metadata = {
                "character_count": len(source_text),
                "line_count": source_text.count("\n") + 1,
                "title": extraction.title,
                "pdf_links": pdf_links,
            }
        elif is_pdf_response(fetched_url):
            extraction = extract_pdf_text(fetched_url.content)
            source_text = extraction.text
            extract_message = "PDF menu text extracted"
            extract_metadata = {
                "character_count": extraction.character_count,
                "line_count": source_text.count("\n") + 1,
                "page_count": extraction.page_count,
                "method": extraction.method,
                "warnings": extraction.warnings,
            }
        else:
            raise UrlImportError("Only HTML menu pages and PDF menu URLs are supported")

        import_record = await self.repository.create_import(
            input_type=ImportInputType.URL,
            source_value=source_text,
            source_filename=fetched_url.final_url,
            status=ImportStatus.PENDING,
        )
        await self.repository.add_event(
            import_record,
            stage="created",
            message="URL import created",
            event_metadata={
                "requested_url": fetched_url.requested_url,
                "final_url": fetched_url.final_url,
            },
        )
        await self.repository.add_event(
            import_record,
            stage="fetch",
            message="URL fetched successfully",
            event_metadata={
                "content_type": fetched_url.content_type,
                "redirect_count": fetched_url.redirect_count,
                "status_code": fetched_url.status_code,
                "byte_count": len(fetched_url.content),
            },
        )
        await self.repository.add_event(
            import_record,
            stage="extract",
            message=extract_message,
            event_metadata=extract_metadata,
        )
        await self.session.commit()
        return await self._extract_import(import_record.id)

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

    async def get_canonical_json(self, import_id: uuid.UUID) -> dict[str, Any]:
        import_record = await self.get_import(import_id)
        if import_record.extracted_menu is None:
            raise ExtractedMenuNotFoundError
        return import_record.extracted_menu.canonical_json

    async def save_corrected_json(self, import_id: uuid.UUID, canonical_json: dict[str, Any]) -> Import:
        import_record = await self.get_import(import_id)
        validated_menu = validate_canonical_menu(canonical_json)
        confidence_score = validated_menu.confidence_score
        extracted_menu = await self.repository.upsert_extracted_menu(
            import_record,
            canonical_json=validated_menu.model_dump(mode="json"),
            validation_status=ValidationStatus.VALID,
            restaurant_name=validated_menu.restaurant,
            currency=validated_menu.currency,
            language=validated_menu.language,
            confidence_score=Decimal(str(confidence_score)) if confidence_score is not None else None,
        )
        await self.repository.update_import_status(import_record, status=ImportStatus.SUCCEEDED)
        await self.repository.add_event(
            import_record,
            stage="validation",
            message="User-corrected JSON saved",
            event_metadata={
                "extracted_menu_id": str(extracted_menu.id),
                "validation_status": ValidationStatus.VALID.value,
            },
        )
        await self.session.commit()
        return await self.get_import(import_id)

    async def _extract_import(self, import_id: uuid.UUID) -> Import:
        import_record = await self.get_import(import_id)
        if not import_record.source_value:
            await self.repository.update_import_status(
                import_record,
                status=ImportStatus.FAILED,
                error_message="Import has no extracted source text",
            )
            await self.repository.add_event(
                import_record,
                stage="ai_extraction",
                message="Menu extraction failed",
                event_metadata={"error": "Import has no extracted source text"},
            )
            await self.session.commit()
            return await self.get_import(import_id)

        await self.repository.update_import_status(import_record, status=ImportStatus.RUNNING)
        await self.repository.add_event(
            import_record,
            stage="ai_extraction",
            message="Menu extraction started",
            event_metadata={"model": self.menu_extraction_service.adapter.model},
        )
        await self.session.commit()

        try:
            result = await self.menu_extraction_service.extract_menu(
                source_text=import_record.source_value,
                input_type=ImportInputType(import_record.input_type),
                source_label=import_record.source_filename,
            )
        except MenuExtractionError as exc:
            error_message = sanitize_error_message(str(exc), fallback="Menu extraction failed")
            import_record = await self.get_import(import_id)
            await self.repository.update_import_status(
                import_record,
                status=ImportStatus.FAILED,
                error_message=error_message,
                model_used=self.menu_extraction_service.adapter.model,
            )
            await self.repository.add_event(
                import_record,
                stage="ai_extraction",
                message="Menu extraction failed",
                event_metadata={"error": error_message},
            )
            await self.session.commit()
            return await self.get_import(import_id)

        import_record = await self.get_import(import_id)
        extracted_menu = await self.repository.upsert_extracted_menu(
            import_record,
            canonical_json=result.menu.model_dump(mode="json"),
            validation_status=ValidationStatus.VALID,
            restaurant_name=result.menu.restaurant,
            currency=result.menu.currency,
            language=result.menu.language,
            confidence_score=result.confidence_decimal,
        )
        await self.repository.update_import_status(
            import_record,
            status=ImportStatus.SUCCEEDED,
            model_used=result.model_used,
        )
        await self.repository.add_event(
            import_record,
            stage="ai_extraction",
            message="Menu extraction succeeded",
            event_metadata={
                "attempts": result.attempts,
                "model": result.model_used,
                "extracted_menu_id": str(extracted_menu.id),
            },
        )
        await self.session.commit()
        return await self.get_import(import_id)


def _build_menu_extraction_service() -> MenuExtractionService:
    settings = get_settings()
    adapter = FakeGeminiAdapter() if settings.gemini_use_fake else HttpGeminiAdapter(settings)
    return MenuExtractionService(adapter=adapter, settings=settings)
