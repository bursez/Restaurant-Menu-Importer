from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
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
        insert_statement = insert(EvaluationCase).values(
            slug=slug,
            name=name,
            source_url=source_url,
            case_set=case_set,
            source_fixture_path=source_fixture_path,
            expected_fixture_path=expected_fixture_path,
            actual_fixture_path=actual_fixture_path,
            qualitative_score=qualitative_score,
            strengths=strengths,
            weaknesses=weaknesses,
            notes=notes,
        )
        upsert_statement = insert_statement.on_conflict_do_update(
            index_elements=[EvaluationCase.slug],
            set_={
                "name": insert_statement.excluded.name,
                "source_url": insert_statement.excluded.source_url,
                "case_set": insert_statement.excluded.case_set,
                "source_fixture_path": insert_statement.excluded.source_fixture_path,
                "expected_fixture_path": insert_statement.excluded.expected_fixture_path,
                "actual_fixture_path": insert_statement.excluded.actual_fixture_path,
                "qualitative_score": insert_statement.excluded.qualitative_score,
                "strengths": insert_statement.excluded.strengths,
                "weaknesses": insert_statement.excluded.weaknesses,
                "notes": insert_statement.excluded.notes,
            },
        ).returning(EvaluationCase)

        result = await self.session.execute(upsert_statement)
        return result.scalar_one()

    async def create_run(self, *, case_set: str, result: dict[str, Any]) -> EvaluationRun:
        run = EvaluationRun(case_set=case_set, result=result)
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run(self, run_id: uuid.UUID) -> EvaluationRun | None:
        result = await self.session.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
        return result.scalar_one_or_none()
