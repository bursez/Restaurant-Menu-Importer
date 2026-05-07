import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import sanitize_error_message
from app.db.session import get_db_session
from app.schemas.imports import CorrectedMenuUpdate, ImportDetailRead, ImportSummaryRead, TextImportCreate, UrlImportCreate
from app.services.html_extraction import HtmlExtractionError
from app.services.imports import ExtractedMenuNotFoundError, ImportNotFoundError, ImportService, UrlImportError
from app.services.pdf_extraction import PdfExtractionError
from app.services.text_imports import MAX_IMPORT_TEXT_LENGTH, TextImportValidationError, validate_text_filename
from app.services.url_fetching import UrlFetchError
from app.services.url_security import UrlValidationError

router = APIRouter(prefix="/api/imports", tags=["imports"])


def get_import_service(session: AsyncSession = Depends(get_db_session)) -> ImportService:
    return ImportService(session)


@router.post("/text", response_model=ImportDetailRead, status_code=status.HTTP_201_CREATED)
async def create_text_import(
    payload: TextImportCreate,
    service: ImportService = Depends(get_import_service),
) -> ImportDetailRead:
    try:
        import_record = await service.create_text_import(
            text=payload.text,
            source_name=payload.source_name,
        )
    except TextImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ImportDetailRead.model_validate(import_record)


@router.post("/file", response_model=ImportDetailRead, status_code=status.HTTP_201_CREATED)
async def create_file_import(
    file: UploadFile = File(...),
    service: ImportService = Depends(get_import_service),
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
        import_record = await service.create_file_import(text=text, filename=filename)
    except TextImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    finally:
        await file.close()

    return ImportDetailRead.model_validate(import_record)


@router.post("/url", response_model=ImportDetailRead, status_code=status.HTTP_201_CREATED)
async def create_url_import(
    payload: UrlImportCreate,
    service: ImportService = Depends(get_import_service),
) -> ImportDetailRead:
    try:
        import_record = await service.create_url_import(url=payload.url)
    except (UrlValidationError, UrlFetchError, UrlImportError, HtmlExtractionError, PdfExtractionError) as exc:
        detail = sanitize_error_message(str(exc), fallback="URL import failed")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    return ImportDetailRead.model_validate(import_record)


@router.get("", response_model=list[ImportSummaryRead])
async def list_imports(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ImportService = Depends(get_import_service),
) -> list[ImportSummaryRead]:
    imports = await service.list_imports(limit=limit, offset=offset)
    return [ImportSummaryRead.model_validate(import_record) for import_record in imports]


@router.get("/{import_id}", response_model=ImportDetailRead)
async def get_import(
    import_id: uuid.UUID,
    service: ImportService = Depends(get_import_service),
) -> ImportDetailRead:
    try:
        import_record = await service.get_import(import_id)
    except ImportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import not found",
        ) from exc
    return ImportDetailRead.model_validate(import_record)


@router.get("/{import_id}/json")
async def download_import_json(
    import_id: uuid.UUID,
    service: ImportService = Depends(get_import_service),
) -> JSONResponse:
    try:
        canonical_json = await service.get_canonical_json(import_id)
    except ImportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found") from exc
    except ExtractedMenuNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extracted menu not found") from exc

    return JSONResponse(
        canonical_json,
        headers={"Content-Disposition": f'attachment; filename="import-{import_id}.json"'},
    )


@router.patch("/{import_id}/json", response_model=ImportDetailRead)
async def save_corrected_import_json(
    import_id: uuid.UUID,
    payload: CorrectedMenuUpdate,
    service: ImportService = Depends(get_import_service),
) -> ImportDetailRead:
    try:
        import_record = await service.save_corrected_json(import_id, payload.canonical_json)
    except ImportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc
    return ImportDetailRead.model_validate(import_record)
