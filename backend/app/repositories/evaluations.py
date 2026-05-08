from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvaluationCase, EvaluationRun


class EvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_cases(self) -> Sequence[EvaluationCase]:
        result = await self.session.execute(
            select(EvaluationCase).order_by(EvaluationCase.case_set.desc(), EvaluationCase.name)
        )
        return result.scalars().all()

    async def upsert_case(
        self,
        *,
        slug: str,
        name: str,
        source_url: str,
        case_set: str,
        source_fixture_path: str | None,
        expected_fixture_path: str | None,
        actual_fixture_path: str | None,
        qualitative_score: Decimal | None,
        strengths: str,
        weaknesses: str,
        notes: str,
    ) -> EvaluationCase:
        result = await self.session.execute(select(EvaluationCase).where(EvaluationCase.slug == slug))
        evaluation_case = result.scalar_one_or_none()
        if evaluation_case is None:
            evaluation_case = EvaluationCase(slug=slug)
            self.session.add(evaluation_case)
        evaluation_case.name = name
        evaluation_case.source_url = source_url
        evaluation_case.case_set = case_set
        evaluation_case.source_fixture_path = source_fixture_path
        evaluation_case.expected_fixture_path = expected_fixture_path
        evaluation_case.actual_fixture_path = actual_fixture_path
        evaluation_case.qualitative_score = qualitative_score
        evaluation_case.strengths = strengths
        evaluation_case.weaknesses = weaknesses
        evaluation_case.notes = notes
        await self.session.flush()
        return evaluation_case

    async def create_run(self, *, case_set: str, result: dict[str, Any]) -> EvaluationRun:
        run = EvaluationRun(case_set=case_set, result=result)
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run(self, run_id: uuid.UUID) -> EvaluationRun | None:
        result = await self.session.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
        return result.scalar_one_or_none()
