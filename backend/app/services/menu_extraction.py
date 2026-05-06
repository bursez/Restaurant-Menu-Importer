from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.domain.imports import ImportInputType
from app.schemas.menu import CanonicalMenu
from app.services.gemini_client import GeminiAdapter, GeminiError
from app.services.gemini_prompt import build_menu_extraction_prompt
from app.services.menu_schema import gemini_menu_json_schema
from app.services.menu_validation import validate_canonical_menu


class MenuExtractionError(Exception):
    pass


@dataclass(frozen=True)
class MenuExtractionResult:
    menu: CanonicalMenu
    model_used: str
    attempts: int

    @property
    def confidence_decimal(self) -> Decimal | None:
        if self.menu.confidence_score is None:
            return None
        return Decimal(str(self.menu.confidence_score))


class MenuExtractionService:
    def __init__(
        self,
        *,
        adapter: GeminiAdapter,
        settings: Settings | None = None,
    ) -> None:
        self.adapter = adapter
        self.settings = settings or get_settings()

    async def extract_menu(
        self,
        *,
        source_text: str,
        input_type: ImportInputType,
        source_label: str | None = None,
    ) -> MenuExtractionResult:
        errors: list[str] = []
        attempts = self.settings.gemini_max_retries + 1
        for attempt in range(1, attempts + 1):
            prompt = build_menu_extraction_prompt(
                source_text=source_text,
                input_type=input_type,
                source_label=source_label,
                previous_errors=errors,
            )
            try:
                raw_response = await self.adapter.generate_structured_menu(
                    prompt=prompt,
                    response_schema=gemini_menu_json_schema(),
                )
                menu = validate_canonical_menu(_with_source(raw_response.payload, input_type, source_label))
                confidence_error = self._confidence_error(menu)
                if confidence_error is None:
                    return MenuExtractionResult(menu=menu, model_used=raw_response.model, attempts=attempt)
                errors = [confidence_error]
            except (GeminiError, ValidationError, ValueError) as exc:
                errors = [_friendly_error(exc)]

        raise MenuExtractionError("; ".join(errors) or "Menu extraction failed")

    def _confidence_error(self, menu: CanonicalMenu) -> str | None:
        confidence = menu.confidence_score
        if confidence is None:
            return "Gemini output did not include confidence_score"
        if confidence < self.settings.gemini_min_confidence:
            return f"Gemini output confidence_score {confidence:.2f} is below {self.settings.gemini_min_confidence:.2f}"
        return None


def _with_source(
    payload: dict[str, Any],
    input_type: ImportInputType,
    source_label: str | None,
) -> dict[str, Any]:
    payload = dict(payload)
    payload["source"] = {
        "type": input_type.value,
        "value": source_label or input_type.value,
    }
    return payload


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "Gemini output failed canonical menu validation"
    return str(exc) or exc.__class__.__name__
