import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.imports import ImportDetailRead, ImportSummaryRead
from app.services.imports import ImportNotFoundError, ImportService

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.get("", response_model=list[ImportSummaryRead])
async def list_imports(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> list[ImportSummaryRead]:
    imports = await ImportService(session).list_imports(limit=limit, offset=offset)
    return [ImportSummaryRead.model_validate(import_record) for import_record in imports]


@router.get("/{import_id}", response_model=ImportDetailRead)
async def get_import(
    import_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ImportDetailRead:
    try:
        import_record = await ImportService(session).get_import(import_id)
    except ImportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import not found",
        ) from exc
    return ImportDetailRead.model_validate(import_record)
