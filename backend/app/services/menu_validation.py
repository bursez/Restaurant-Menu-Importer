from __future__ import annotations

import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from app.schemas.menu import CanonicalMenu

PRICE_PATTERN = re.compile(
    r"""
    (?P<currency>€|eur)?\s*
    (?P<amount>\d{1,3}(?:[.,]\d{2})?)
    (?:/(?P<unit>[a-zA-Z]{1,8}))?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def validate_canonical_menu(raw_menu: dict[str, Any]) -> CanonicalMenu:
    normalized = normalize_menu_structure(raw_menu)
    normalized = normalize_menu_prices(normalized)
    return CanonicalMenu.model_validate(normalized)


def normalize_menu_structure(raw_menu: dict[str, Any]) -> dict[str, Any]:
    menu = deepcopy(raw_menu)
    _cleanup_menu_text(menu)
    categories = menu.get("categories")
    if isinstance(categories, list) and all(isinstance(category, dict) for category in categories):
        menu["categories"] = _deduplicate_categories(categories)
    return menu


def normalize_menu_prices(raw_menu: dict[str, Any]) -> dict[str, Any]:
    menu = deepcopy(raw_menu)
    for category in _list_of_dicts(menu.get("categories")):
        items = category.get("items")
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            continue
        for item in items:
            _normalize_price_fields(item)
            if item.get("price") is None and item.get("price_text"):
                _build_variants_from_price_text(item)
            variants = item.get("variants")
            if not isinstance(variants, list) or not all(isinstance(variant, dict) for variant in variants):
                continue
            for variant in variants:
                _normalize_price_fields(variant)
    return menu


def parse_price_text(price_text: str | None) -> float | None:
    prices = parse_price_segments(price_text)
    return prices[0]["price"] if len(prices) == 1 else None


def parse_price_segments(price_text: str | None) -> list[dict[str, Any]]:
    if not price_text:
        return []

    segments: list[dict[str, Any]] = []
    for match in PRICE_PATTERN.finditer(price_text):
        amount = _amount_to_float(match.group("amount"))
        if amount is None:
            continue
        segments.append(
            {
                "price": amount,
                "price_text": match.group(0).strip(),
                "unit": match.group("unit"),
            }
        )
    return segments


def _cleanup_menu_text(menu: dict[str, Any]) -> None:
    _clean_string_field(menu, "restaurant")
    _clean_string_field(menu, "currency", uppercase=True)
    _clean_string_field(menu, "language", lowercase=True)
    source = menu.get("source")
    if isinstance(source, dict):
        _clean_string_field(source, "value")

    categories = menu.get("categories")
    if not isinstance(categories, list) or not all(isinstance(category, dict) for category in categories):
        return

    for category in categories:
        _clean_string_field(category, "name")
        items = category.get("items")
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            continue
        for item in items:
            _clean_string_field(item, "name")
            _clean_string_field(item, "description")
            _clean_string_field(item, "price_text")
            item["allergens"] = _clean_string_list(item.get("allergens"))
            item["tags"] = _clean_string_list(item.get("tags"))
            variants = item.get("variants")
            if not isinstance(variants, list) or not all(isinstance(variant, dict) for variant in variants):
                continue
            for variant in variants:
                _clean_string_field(variant, "name")
                _clean_string_field(variant, "price_text")


def _deduplicate_categories(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for category in categories:
        key = _dedupe_key(category.get("name"))
        if not key:
            continue
        items = category.get("items")
        if isinstance(items, list) and all(isinstance(item, dict) for item in items):
            category["items"] = _deduplicate_items(items)
        if key not in deduped:
            deduped[key] = category
            continue
        existing_items = _list_of_dicts(deduped[key].get("items"))
        existing_items.extend(_list_of_dicts(category.get("items")))
        deduped[key]["items"] = _deduplicate_items(existing_items)
    return list(deduped.values())


def _deduplicate_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for item in items:
        key = _item_dedupe_key(item)
        if not key:
            continue
        if key not in deduped:
            deduped[key] = item
            continue
        deduped[key] = _merge_item(deduped[key], item)
    return list(deduped.values())


def _merge_item(existing: dict[str, Any], duplicate: dict[str, Any]) -> dict[str, Any]:
    for field in ("description", "price_text", "price"):
        if existing.get(field) in (None, "") and duplicate.get(field) not in (None, ""):
            existing[field] = duplicate[field]
    existing["allergens"] = _clean_string_list(
        [*_raw_list(existing.get("allergens")), *_raw_list(duplicate.get("allergens"))]
    )
    existing["tags"] = _clean_string_list([*_raw_list(existing.get("tags")), *_raw_list(duplicate.get("tags"))])
    variants = [*_list_of_dicts(existing.get("variants")), *_list_of_dicts(duplicate.get("variants"))]
    existing["variants"] = _deduplicate_variants(variants)
    return existing


def _deduplicate_variants(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for variant in variants:
        key = "|".join(
            [
                _dedupe_key(variant.get("name")),
                _dedupe_key(variant.get("price_text")),
                str(variant.get("price") or ""),
            ]
        )
        if key.strip("|"):
            deduped.setdefault(key, variant)
    return list(deduped.values())


def _normalize_price_fields(node: dict[str, Any]) -> None:
    price = node.get("price")
    if isinstance(price, str):
        node["price_text"] = node.get("price_text") or price
        node["price"] = parse_price_text(price)
        return

    if price is None:
        parsed_price = parse_price_text(_optional_string(node.get("price_text")))
        if parsed_price is not None:
            node["price"] = parsed_price
        else:
            node["price"] = None
        return

    if isinstance(price, (int, float, Decimal)):
        node["price"] = _amount_to_float(str(price))


def _build_variants_from_price_text(item: dict[str, Any]) -> None:
    if item.get("variants"):
        return

    prices = parse_price_segments(_optional_string(item.get("price_text")))
    if len(prices) < 2:
        return

    item["variants"] = [
        {
            "name": _variant_name(index, price),
            "price": price["price"],
            "price_text": price["price_text"],
        }
        for index, price in enumerate(prices, start=1)
    ]


def _amount_to_float(amount: str) -> float | None:
    normalized = amount.strip().replace(",", ".")
    try:
        decimal = Decimal(normalized)
    except InvalidOperation:
        return None
    rounded = decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(rounded)


def _variant_name(index: int, price: dict[str, Any]) -> str:
    unit = price.get("unit")
    if unit:
        return f"Option {index} / {unit}"
    return f"Option {index}"


def _clean_string_field(node: dict[str, Any], field: str, *, uppercase: bool = False, lowercase: bool = False) -> None:
    value = node.get(field)
    if not isinstance(value, str):
        return
    cleaned = _collapse_whitespace(value)
    if uppercase:
        cleaned = cleaned.upper()
    if lowercase:
        cleaned = cleaned.lower()
    node[field] = cleaned


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: dict[str, str] = {}
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = _collapse_whitespace(item).lower()
        if normalized:
            cleaned.setdefault(normalized, normalized)
    return list(cleaned.values())


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _item_dedupe_key(item: dict[str, Any]) -> str:
    return "|".join(
        [
            _dedupe_key(item.get("name")),
            _dedupe_key(item.get("price_text")),
            str(item.get("price") or ""),
        ]
    ).strip("|")


def _dedupe_key(value: Any) -> str:
    return _collapse_whitespace(value).casefold() if isinstance(value, str) else ""


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _raw_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None
