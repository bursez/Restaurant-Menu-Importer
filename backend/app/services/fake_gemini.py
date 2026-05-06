from __future__ import annotations

import re
from typing import Any

from app.services.gemini_client import GeminiRawResponse

PRICE_LINE_PATTERN = re.compile(r"^(?P<name>.+?)\s+(?P<price>€?\s*\d{1,3}(?:[,.]\d{2})?)$")
SOURCE_BLOCK_PATTERN = re.compile(r'Menu source:\s+"""(?P<source>.*?)"""', re.DOTALL)
SOURCE_TYPE_PATTERN = re.compile(r"Source type:\s*(?P<type>\w+)")
SOURCE_NAME_PATTERN = re.compile(r"Source name:\s*(?P<name>.+)")


class FakeGeminiAdapter:
    model = "fake-gemini-menu-extractor"

    async def generate_structured_menu(
        self,
        *,
        prompt: str,
        response_schema: dict[str, Any],
    ) -> GeminiRawResponse:
        del response_schema
        source_text = _extract_source_text(prompt)
        source_type = _extract_match(prompt, SOURCE_TYPE_PATTERN) or "text"
        source_name = _extract_match(prompt, SOURCE_NAME_PATTERN) or source_type
        return GeminiRawResponse(
            payload={
                "restaurant": _restaurant_name(source_text, source_name),
                "currency": "EUR" if "€" in source_text or "eur" in source_text.casefold() else None,
                "language": "it",
                "source": {"type": source_type, "value": source_name},
                "categories": _categories(source_text),
                "confidence_score": 0.86,
                "validation_warnings": [],
            },
            model=self.model,
        )


def _extract_source_text(prompt: str) -> str:
    match = SOURCE_BLOCK_PATTERN.search(prompt)
    return match.group("source").strip() if match else prompt


def _extract_match(prompt: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(prompt)
    return match.group(1).strip() if match else None


def _restaurant_name(source_text: str, source_name: str) -> str:
    for line in source_text.splitlines():
        cleaned = line.strip("# ").strip()
        if cleaned and not PRICE_LINE_PATTERN.match(cleaned):
            return cleaned[:120]
    return source_name[:120]


def _categories(source_text: str) -> list[dict[str, Any]]:
    categories: list[dict[str, Any]] = []
    current_category: dict[str, Any] = {"name": "Menu", "items": []}

    for line in source_text.splitlines():
        cleaned = line.strip().strip("-").strip()
        if not cleaned:
            continue
        price_match = PRICE_LINE_PATTERN.match(cleaned)
        if price_match:
            current_category["items"].append(
                {
                    "name": price_match.group("name").strip(),
                    "description": None,
                    "price": None,
                    "price_text": price_match.group("price").strip(),
                    "allergens": [],
                    "tags": [],
                    "variants": [],
                }
            )
            continue

        if current_category["items"]:
            categories.append(current_category)
            current_category = {"name": cleaned[:120], "items": []}
        elif not categories:
            current_category["name"] = cleaned[:120]

    if current_category["items"]:
        categories.append(current_category)
    if categories:
        return categories
    return [{"name": "Menu", "items": []}]
