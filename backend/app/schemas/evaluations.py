from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EvaluationCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    source_url: str
    case_set: str
    source_fixture_path: str | None
    expected_fixture_path: str | None
    actual_fixture_path: str | None
    qualitative_score: Decimal | None
    strengths: str | None
    weaknesses: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class EvaluationRunCreate(BaseModel):
    case_set: Literal["required", "full"] = "full"


class EvaluationCaseMetric(BaseModel):
    slug: str
    name: str
    case_set: str
    is_valid: bool
    category_coverage: float | None
    item_count_ratio: float | None
    price_coverage: float
    language_score: float | None
    qualitative_score: float | None
    strengths: str | None
    weaknesses: str | None
    notes: str | None
    errors: list[str] = Field(default_factory=list)


class EvaluationRunRead(BaseModel):
    id: uuid.UUID
    case_set: str
    case_count: int
    averages: dict[str, float | None]
    cases: list[EvaluationCaseMetric]
    created_at: datetime


class EvaluationRunStoredRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_set: str
    result: dict[str, Any]
    created_at: datetime
