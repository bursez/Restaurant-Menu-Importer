from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvaluationCase
from app.domain.evaluations import EvaluationCaseSet
from app.repositories.evaluations import EvaluationRepository
from app.schemas.evaluations import EvaluationCaseMetric, EvaluationRunRead
from app.schemas.menu import CanonicalMenu, MenuItem
from app.services.evaluation_seed import EVALUATION_CASES


class EvaluationRunNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class MenuStats:
    category_names: set[str]
    item_count: int
    priced_item_count: int
    language: str | None


class EvaluationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = EvaluationRepository(session)
        self.fixture_root = Path(__file__).resolve().parents[2]

    async def list_cases(self) -> Sequence[EvaluationCase]:
        await self.seed_cases()
        return await self.repository.list_cases()

    async def run(self, *, case_set: str) -> EvaluationRunRead:
        await self.seed_cases()
        cases = await self.repository.list_cases()
        selected_cases = [
            evaluation_case
            for evaluation_case in cases
            if case_set == EvaluationCaseSet.FULL or evaluation_case.case_set == case_set
        ]
        metrics = [self._score_case(evaluation_case) for evaluation_case in selected_cases]
        averages = self._averages(metrics)
        run_result = {
            "case_count": len(metrics),
            "averages": averages,
            "cases": [metric.model_dump(mode="json") for metric in metrics],
        }
        run = await self.repository.create_run(case_set=case_set, result=run_result)
        await self.session.commit()
        return EvaluationRunRead(
            id=run.id,
            case_set=case_set,
            case_count=len(metrics),
            averages=averages,
            cases=metrics,
            created_at=run.created_at,
        )

    async def get_run(self, run_id: uuid.UUID) -> EvaluationRunRead:
        run = await self.repository.get_run(run_id)
        if run is None:
            raise EvaluationRunNotFoundError
        return EvaluationRunRead(
            id=run.id,
            case_set=run.case_set,
            case_count=int(run.result["case_count"]),
            averages=run.result["averages"],
            cases=[EvaluationCaseMetric.model_validate(metric) for metric in run.result["cases"]],
            created_at=run.created_at,
        )

    async def seed_cases(self) -> None:
        for case in EVALUATION_CASES:
            await self.repository.upsert_case(**case)
        await self.session.commit()

    def _score_case(self, evaluation_case: EvaluationCase) -> EvaluationCaseMetric:
        errors: list[str] = []
        expected_menu = self._load_menu(evaluation_case.expected_fixture_path, errors)
        actual_menu = self._load_menu(evaluation_case.actual_fixture_path, errors)

        is_valid = actual_menu is not None
        if actual_menu is None:
            return EvaluationCaseMetric(
                slug=evaluation_case.slug,
                name=evaluation_case.name,
                case_set=evaluation_case.case_set,
                is_valid=False,
                category_coverage=None,
                item_count_ratio=None,
                price_coverage=0,
                language_score=None,
                qualitative_score=self._decimal_to_float(evaluation_case.qualitative_score),
                strengths=evaluation_case.strengths,
                weaknesses=evaluation_case.weaknesses,
                notes=evaluation_case.notes,
                errors=errors,
            )

        actual_stats = self._stats(actual_menu)
        expected_stats = self._stats(expected_menu) if expected_menu is not None else None
        category_coverage = self._category_coverage(expected_stats, actual_stats)
        item_count_ratio = self._item_count_ratio(expected_stats, actual_stats)
        language_score = self._language_score(expected_stats, actual_stats)

        return EvaluationCaseMetric(
            slug=evaluation_case.slug,
            name=evaluation_case.name,
            case_set=evaluation_case.case_set,
            is_valid=is_valid,
            category_coverage=category_coverage,
            item_count_ratio=item_count_ratio,
            price_coverage=self._safe_ratio(actual_stats.priced_item_count, actual_stats.item_count),
            language_score=language_score,
            qualitative_score=self._decimal_to_float(evaluation_case.qualitative_score),
            strengths=evaluation_case.strengths,
            weaknesses=evaluation_case.weaknesses,
            notes=evaluation_case.notes,
            errors=errors,
        )

    def _load_menu(self, fixture_path: str | None, errors: list[str]) -> CanonicalMenu | None:
        if fixture_path is None:
            return None
        path = self.fixture_root / fixture_path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return CanonicalMenu.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            errors.append(f"{fixture_path}: {exc}")
            return None

    def _stats(self, menu: CanonicalMenu | None) -> MenuStats:
        if menu is None:
            return MenuStats(category_names=set(), item_count=0, priced_item_count=0, language=None)
        items = [item for category in menu.categories for item in category.items]
        return MenuStats(
            category_names={self._normalize_name(category.name) for category in menu.categories},
            item_count=len(items),
            priced_item_count=sum(1 for item in items if self._has_price(item)),
            language=menu.language,
        )

    def _category_coverage(self, expected_stats: MenuStats | None, actual_stats: MenuStats) -> float | None:
        if expected_stats is None or not expected_stats.category_names:
            return None
        matched = expected_stats.category_names.intersection(actual_stats.category_names)
        return self._safe_ratio(len(matched), len(expected_stats.category_names))

    def _item_count_ratio(self, expected_stats: MenuStats | None, actual_stats: MenuStats) -> float | None:
        if expected_stats is None or expected_stats.item_count == 0:
            return None
        ratio = actual_stats.item_count / expected_stats.item_count
        return round(min(ratio, 1 / ratio) if ratio else 0, 2)

    def _language_score(self, expected_stats: MenuStats | None, actual_stats: MenuStats) -> float | None:
        if expected_stats is None or expected_stats.language is None:
            return None
        return 1.0 if expected_stats.language == actual_stats.language else 0.0

    def _averages(self, metrics: list[EvaluationCaseMetric]) -> dict[str, float | None]:
        return {
            "validity": self._average([1.0 if metric.is_valid else 0.0 for metric in metrics]),
            "category_coverage": self._average_optional([metric.category_coverage for metric in metrics]),
            "item_count_ratio": self._average_optional([metric.item_count_ratio for metric in metrics]),
            "price_coverage": self._average([metric.price_coverage for metric in metrics]),
            "language_score": self._average_optional([metric.language_score for metric in metrics]),
            "qualitative_score": self._average_optional([metric.qualitative_score for metric in metrics]),
        }

    def _average_optional(self, values: list[float | None]) -> float | None:
        return self._average([value for value in values if value is not None])

    def _average(self, values: list[float]) -> float | None:
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    def _safe_ratio(self, numerator: int, denominator: int) -> float:
        if denominator == 0:
            return 0
        return round(numerator / denominator, 2)

    def _has_price(self, item: MenuItem) -> bool:
        if item.price is not None:
            return True
        return any(variant.price is not None for variant in item.variants)

    def _normalize_name(self, value: str) -> str:
        return " ".join(value.casefold().split())

    def _decimal_to_float(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None
