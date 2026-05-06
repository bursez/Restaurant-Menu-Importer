from httpx import ASGITransport, AsyncClient
import pytest

from app.domain.imports import ImportInputType, ImportStatus, ValidationStatus
from app.services.imports import ImportService


def menu_payload(name: str = "Demo") -> dict:
    return {
        "restaurant": name,
        "currency": "EUR",
        "language": "it",
        "source": {"type": "text", "value": "Antipasti\nBruschetta 6,50"},
        "categories": [
            {
                "name": "Antipasti",
                "items": [
                    {
                        "name": "Bruschetta",
                        "description": "Tomato toast",
                        "price": 6.5,
                        "price_text": "€ 6,50",
                        "allergens": ["gluten"],
                        "tags": ["vegetarian"],
                        "variants": [],
                    }
                ],
            }
        ],
        "confidence_score": 0.9,
        "validation_warnings": [],
    }


@pytest.mark.asyncio
async def test_create_text_import_normalizes_and_persists_text(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/imports/text",
            json={
                "text": " Antipasti\r\n\r\n\r\n• Bruschetta\u00a0  € 6,50 ",
                "source_name": "dinner menu",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["input_type"] == "text"
    assert payload["source_filename"] == "dinner menu"
    assert payload["source_value"] == "Antipasti\n\n- Bruschetta € 6,50"
    assert payload["status"] == "succeeded"
    assert payload["model_used"] == "fake-gemini-menu-extractor"
    assert payload["extracted_menu"]["restaurant_name"] == "Antipasti"
    assert payload["extracted_menu"]["canonical_json"]["categories"][0]["items"][0]["price"] == 6.5
    assert [event["stage"] for event in payload["events"]] == ["created", "ai_extraction", "ai_extraction"]


@pytest.mark.asyncio
async def test_create_text_import_rejects_blank_text(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/imports/text", json={"text": " \n \t "})

    assert response.status_code == 422
    assert response.json() == {"detail": "Import text cannot be empty"}


@pytest.mark.asyncio
async def test_create_file_import_accepts_markdown(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/imports/file",
            files={"file": ("menu.md", b"# Menu\n\nMargherita 7.50", "text/markdown")},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["input_type"] == "file"
    assert payload["source_filename"] == "menu.md"
    assert payload["source_value"] == "# Menu\n\nMargherita 7.50"
    assert payload["status"] == "succeeded"
    assert payload["extracted_menu"]["canonical_json"]["categories"][0]["items"][0]["name"] == "Margherita"


@pytest.mark.asyncio
async def test_create_file_import_rejects_unsupported_extensions(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/imports/file",
            files={"file": ("menu.pdf", b"%PDF", "application/pdf")},
        )

    assert response.status_code == 422
    assert response.json() == {"detail": "Only .txt and .md menu files are supported"}


@pytest.mark.asyncio
async def test_list_and_get_imports(app, db_session) -> None:
    service = ImportService(db_session)
    import_record = await service.create_import(
        input_type=ImportInputType.TEXT,
        source_value="Antipasti\nBruschetta 6,50",
    )
    await service.update_status(import_record.id, status=ImportStatus.RUNNING)
    await service.save_extracted_menu(
        import_record.id,
        canonical_json=menu_payload(),
        validation_status=ValidationStatus.VALID,
        restaurant_name="Demo",
        currency="EUR",
        language="it",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        list_response = await client.get("/api/imports")
        detail_response = await client.get(f"/api/imports/{import_record.id}")

    assert list_response.status_code == 200
    imports = list_response.json()
    assert len(imports) == 1
    assert imports[0]["id"] == str(import_record.id)
    assert imports[0]["status"] == "running"
    assert imports[0]["extracted_menu"]["restaurant_name"] == "Demo"

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["source_value"] == "Antipasti\nBruschetta 6,50"
    assert [event["stage"] for event in detail["events"]] == ["created", "status", "validation"]


@pytest.mark.asyncio
async def test_get_import_returns_404_for_missing_uuid(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/imports/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json() == {"detail": "Import not found"}


@pytest.mark.asyncio
async def test_download_import_json(app, db_session) -> None:
    service = ImportService(db_session)
    import_record = await service.create_import(
        input_type=ImportInputType.TEXT,
        source_value="Antipasti\nBruschetta 6,50",
    )
    await service.save_extracted_menu(
        import_record.id,
        canonical_json=menu_payload(),
        validation_status=ValidationStatus.VALID,
        restaurant_name="Demo",
        currency="EUR",
        language="it",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(f"/api/imports/{import_record.id}/json")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f'attachment; filename="import-{import_record.id}.json"'
    assert response.json()["restaurant"] == "Demo"


@pytest.mark.asyncio
async def test_patch_import_json_validates_and_saves_corrections(app, db_session) -> None:
    service = ImportService(db_session)
    import_record = await service.create_import(
        input_type=ImportInputType.TEXT,
        source_value="Antipasti\nBruschetta 6,50",
    )

    corrected_json = menu_payload("Corrected Restaurant")
    corrected_json["categories"][0]["items"][0]["price_text"] = "6,50"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.patch(
            f"/api/imports/{import_record.id}/json",
            json={"canonical_json": corrected_json},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["extracted_menu"]["restaurant_name"] == "Corrected Restaurant"
    assert payload["extracted_menu"]["canonical_json"]["categories"][0]["items"][0]["price"] == 6.5
    assert payload["events"][-1]["message"] == "User-corrected JSON saved"


@pytest.mark.asyncio
async def test_patch_import_json_rejects_invalid_menu(app, db_session) -> None:
    service = ImportService(db_session)
    import_record = await service.create_import(input_type=ImportInputType.TEXT, source_value="Broken")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.patch(
            f"/api/imports/{import_record.id}/json",
            json={"canonical_json": {"restaurant": "", "categories": []}},
        )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["restaurant"]
