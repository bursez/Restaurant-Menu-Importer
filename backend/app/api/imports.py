import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.imports import ImportDetailRead, ImportSummaryRead, TextImportCreate, UrlImportCreate
from app.services.html_extraction import HtmlExtractionError
from app.services.imports import ImportNotFoundError, ImportService, UrlImportError
from app.services.pdf_extraction import PdfExtractionError
from app.services.text_imports import MAX_IMPORT_TEXT_LENGTH, TextImportValidationError, validate_text_filename
from app.services.url_fetching import UrlFetchError
from app.services.url_security import UrlValidationError

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.post("/text", response_model=ImportDetailRead, status_code=status.HTTP_201_CREATED)
async def create_text_import(
    payload: TextImportCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ImportDetailRead:
    try:
        import_record = await ImportService(session).create_text_import(
            text=payload.text,
            source_name=payload.source_name,
        )
    except TextImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ImportDetailRead.model_validate(import_record)


@router.post("/file", response_model=ImportDetailRead, status_code=status.HTTP_201_CREATED)
async def create_file_import(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> ImportDetailRead:
    try:
        filename = validate_text_filename(file.filename)
        contents = await file.read(MAX_IMPORT_TEXT_LENGTH + 1)
        if len(contents) > MAX_IMPORT_TEXT_LENGTH:
            raise TextImportValidationError(f"Import text cannot exceed {MAX_IMPORT_TEXT_LENGTH} characters")
        try:
            text = contents.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TextImportValidationError("Uploaded menu files must be UTF-8 encoded") from exc
        import_record = await ImportService(session).create_file_import(text=text, filename=filename)
    except TextImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    finally:
        await file.close()

    return ImportDetailRead.model_validate(import_record)


@router.post("/url", response_model=ImportDetailRead, status_code=status.HTTP_201_CREATED)
async def create_url_import(
    payload: UrlImportCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ImportDetailRead:
    try:
        import_record = await ImportService(session).create_url_import(url=payload.url)
    except (UrlValidationError, UrlFetchError, UrlImportError, HtmlExtractionError, PdfExtractionError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ImportDetailRead.model_validate(import_record)


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
