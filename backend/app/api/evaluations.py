import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.evaluations import EvaluationCaseRead, EvaluationRunCreate, EvaluationRunRead
from app.services.evaluations import EvaluationRunNotFoundError, EvaluationService

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


def get_evaluation_service(session: AsyncSession = Depends(get_db_session)) -> EvaluationService:
    return EvaluationService(session)


@router.get("/cases", response_model=list[EvaluationCaseRead])
async def list_evaluation_cases(
    service: EvaluationService = Depends(get_evaluation_service),
) -> list[EvaluationCaseRead]:
    cases = await service.list_cases()
    return [EvaluationCaseRead.model_validate(evaluation_case) for evaluation_case in cases]


@router.post("/run", response_model=EvaluationRunRead)
async def run_evaluation(
    payload: EvaluationRunCreate,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationRunRead:
    return await service.run(case_set=payload.case_set)


@router.get("/{run_id}", response_model=EvaluationRunRead)
async def get_evaluation_run(
    run_id: uuid.UUID,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationRunRead:
    try:
        return await service.get_run(run_id)
    except EvaluationRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found") from exc
