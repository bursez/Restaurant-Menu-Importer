from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExtractedMenuRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    restaurant_name: str | None
    currency: str | None
    language: str | None
    confidence_score: Decimal | None
    validation_status: str
    canonical_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ImportEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage: str
    message: str
    event_metadata: dict[str, Any]
    created_at: datetime


class ImportSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    input_type: str
    source_value: str | None
    source_filename: str | None
    status: str
    error_message: str | None
    model_used: str | None
    duration_ms: int | None
    created_at: datetime
    updated_at: datetime
    extracted_menu: ExtractedMenuRead | None = None


class ImportDetailRead(ImportSummaryRead):
    events: list[ImportEventRead] = Field(default_factory=list)
