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
    (?:\s*/\s*(?P<unit>[a-zA-Z]{1,8}))?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def validate_canonical_menu(raw_menu: dict[str, Any]) -> CanonicalMenu:
    normalized = normalize_menu_prices(raw_menu)
    return CanonicalMenu.model_validate(normalized)


def normalize_menu_prices(raw_menu: dict[str, Any]) -> dict[str, Any]:
    menu = deepcopy(raw_menu)
    for category in _list_of_dicts(menu.get("categories")):
        for item in _list_of_dicts(category.get("items")):
            _normalize_price_fields(item)
            if item.get("price") is None and item.get("price_text"):
                _build_variants_from_price_text(item)
            for variant in _list_of_dicts(item.get("variants")):
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


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None
