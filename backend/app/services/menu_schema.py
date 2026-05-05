from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.schemas.menu import CanonicalMenu


def gemini_menu_json_schema() -> dict[str, Any]:
    """Return the canonical menu schema in a Gemini-friendly shape."""
    schema = deepcopy(CanonicalMenu.model_json_schema(mode="validation"))
    _remove_unsupported_schema_keys(schema)
    schema["additionalProperties"] = False
    return schema


def _remove_unsupported_schema_keys(value: Any) -> None:
    if isinstance(value, dict):
        value.pop("default", None)
        value.pop("title", None)
        for child in value.values():
            _remove_unsupported_schema_keys(child)
    elif isinstance(value, list):
        for child in value:
            _remove_unsupported_schema_keys(child)
