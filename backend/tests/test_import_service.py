from typing import Any

import pytest

from app.domain.imports import ImportInputType, ImportStatus
from app.services.gemini_client import GeminiRawResponse
from app.services.imports import ImportService
from app.services.menu_extraction import MenuExtractionService


class FailingGeminiAdapter:
    model = "failing-gemini"

    async def generate_structured_menu(
        self,
        *,
        prompt: str,
        response_schema: dict[str, Any],
    ) -> GeminiRawResponse:
        return GeminiRawResponse(payload={"restaurant": "", "categories": []}, model=self.model)


@pytest.mark.asyncio
async def test_import_service_creates_status_updates_and_events(db_session) -> None:
    service = ImportService(db_session)

    import_record = await service.create_import(
        input_type=ImportInputType.FILE,
        source_filename="menu.md",
    )
    await service.record_event(
        import_record.id,
        stage="extract",
        message="Text extracted",
        event_metadata={"lines": 12},
    )
    await service.update_status(
        import_record.id,
        status=ImportStatus.FAILED,
        error_message="Validation failed",
    )

    reloaded = await service.get_import(import_record.id)

    assert reloaded.input_type == "file"
    assert reloaded.source_filename == "menu.md"
    assert reloaded.status == "failed"
    assert reloaded.error_message == "Validation failed"
    assert [(event.stage, event.message) for event in reloaded.events] == [
        ("created", "file import created"),
        ("extract", "Text extracted"),
        ("status", "Import marked failed"),
    ]
    assert reloaded.events[1].event_metadata == {"lines": 12}


@pytest.mark.asyncio
async def test_import_service_stores_gemini_failures(db_session) -> None:
    service = ImportService(
        db_session,
        menu_extraction_service=MenuExtractionService(
            adapter=FailingGeminiAdapter(),
        ),
    )

    import_record = await service.create_text_import(text="Trattoria Demo\nBruschetta € 6,50")

    assert import_record.status == "failed"
    assert import_record.model_used == "failing-gemini"
    assert import_record.error_message
    assert import_record.events[-1].message == "Menu extraction failed"
