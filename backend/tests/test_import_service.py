import pytest

from app.domain.imports import ImportInputType, ImportStatus
from app.services.imports import ImportService


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
