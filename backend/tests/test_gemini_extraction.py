from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.domain.imports import ImportInputType
from app.services.gemini_client import GeminiRawResponse
from app.services.menu_extraction import MenuExtractionError, MenuExtractionService


class SequenceGeminiAdapter:
    model = "sequence-gemini"

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = payloads
        self.calls = 0

    async def generate_structured_menu(
        self,
        *,
        prompt: str,
        response_schema: dict[str, Any],
    ) -> GeminiRawResponse:
        assert "Menu source:" in prompt
        assert response_schema["type"] == "object"
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return GeminiRawResponse(payload=payload, model=self.model)


def valid_payload(*, confidence_score: float = 0.9) -> dict[str, Any]:
    return {
        "restaurant": "Trattoria Demo",
        "currency": "EUR",
        "language": "it",
        "source": {"type": "text", "value": "demo"},
        "categories": [
            {
                "name": "Antipasti",
                "items": [
                    {
                        "name": "Bruschetta",
                        "description": None,
                        "price": None,
                        "price_text": "€ 6,50",
                        "allergens": [],
                        "tags": [],
                        "variants": [],
                    }
                ],
            }
        ],
        "confidence_score": confidence_score,
        "validation_warnings": [],
    }


@pytest.mark.asyncio
async def test_menu_extraction_succeeds_with_structured_output() -> None:
    adapter = SequenceGeminiAdapter([valid_payload()])
    service = MenuExtractionService(adapter=adapter, settings=Settings(gemini_max_retries=0))

    result = await service.extract_menu(
        source_text="Trattoria Demo\nAntipasti\nBruschetta € 6,50",
        input_type=ImportInputType.TEXT,
        source_label="demo",
    )

    assert result.menu.restaurant == "Trattoria Demo"
    assert result.menu.categories[0].items[0].price == 6.5
    assert result.model_used == "sequence-gemini"
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_menu_extraction_retries_after_validation_failure() -> None:
    adapter = SequenceGeminiAdapter(
        [
            {"restaurant": "", "categories": [], "confidence_score": 0.9},
            valid_payload(),
        ]
    )
    service = MenuExtractionService(adapter=adapter, settings=Settings(gemini_max_retries=1))

    result = await service.extract_menu(
        source_text="Trattoria Demo\nBruschetta € 6,50",
        input_type=ImportInputType.TEXT,
    )

    assert adapter.calls == 2
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_menu_extraction_fails_after_low_confidence_retries() -> None:
    adapter = SequenceGeminiAdapter([valid_payload(confidence_score=0.2)])
    service = MenuExtractionService(
        adapter=adapter,
        settings=Settings(gemini_max_retries=1, gemini_min_confidence=0.55),
    )

    with pytest.raises(MenuExtractionError, match="below 0.55"):
        await service.extract_menu(
            source_text="Trattoria Demo\nBruschetta € 6,50",
            input_type=ImportInputType.TEXT,
        )

    assert adapter.calls == 2
