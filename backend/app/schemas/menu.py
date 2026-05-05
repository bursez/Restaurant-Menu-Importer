from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MenuSourceType(StrEnum):
    TEXT = "text"
    URL = "url"
    FILE = "file"


class ValidationWarningCode(StrEnum):
    MISSING_PRICE = "missing_price"
    UNKNOWN_CURRENCY = "unknown_currency"
    DUPLICATE_CATEGORY = "duplicate_category"
    DUPLICATE_ITEM = "duplicate_item"
    LOW_CONFIDENCE = "low_confidence"
    NORMALIZED_PRICE = "normalized_price"


class MenuSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: MenuSourceType
    value: str = Field(min_length=1)


class ValidationWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ValidationWarningCode
    message: str = Field(min_length=1)
    path: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class MenuVariant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    price: Decimal | None = None
    price_text: str | None = None

    @field_validator("price")
    @classmethod
    def price_cannot_be_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            msg = "Price cannot be negative"
            raise ValueError(msg)
        return value


class MenuItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    price: Decimal | None = None
    price_text: str | None = None
    allergens: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    variants: list[MenuVariant] = Field(default_factory=list)

    @field_validator("price")
    @classmethod
    def price_cannot_be_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            msg = "Price cannot be negative"
            raise ValueError(msg)
        return value


class MenuCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    items: list[MenuItem] = Field(default_factory=list)


class CanonicalMenu(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restaurant: str = Field(min_length=1)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    language: str | None = Field(default=None, min_length=2, max_length=16)
    source: MenuSource
    categories: list[MenuCategory] = Field(default_factory=list)
    confidence_score: Decimal | None = Field(default=None, ge=0, le=1)
    validation_warnings: list[ValidationWarning] = Field(default_factory=list)

    @field_validator("currency")
    @classmethod
    def currency_is_uppercase(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value

    @field_validator("language")
    @classmethod
    def language_is_lowercase(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else value


GeminiCanonicalMenu = CanonicalMenu
CanonicalMenuJson = dict[str, Any]
ValidationWarningPath = str
SupportedCurrency = Literal["EUR"]
