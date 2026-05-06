from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import re
import subprocess
import tempfile

import fitz
from PIL import Image
import pdfplumber
import pytesseract

from app.services.text_imports import normalize_import_text


MIN_TEXT_CHARACTERS = 40
MAX_OCR_PAGES = 20
PRICE_PATTERN = re.compile(r"(?:€\s*)?\d{1,3}(?:[.,]\d{2})?(?:\s*€)?")


class PdfExtractionError(ValueError):
    pass


@dataclass(frozen=True)
class PdfPageText:
    page_number: int
    text: str
    line_count: int


@dataclass(frozen=True)
class PdfExtractionResult:
    text: str
    pages: list[PdfPageText]
    method: str
    warnings: list[str] = field(default_factory=list)

    @property
    def character_count(self) -> int:
        return len(self.text)

    @property
    def page_count(self) -> int:
        return len(self.pages)


def _format_pages(pages: list[PdfPageText]) -> str:
    sections: list[str] = []
    for page in pages:
        if page.text:
            sections.append(f"[Page {page.page_number}]\n{page.text}")
    return "\n\n".join(sections)


def _page_text(page_number: int, text: str) -> PdfPageText:
    normalized = normalize_import_text(text) if text.strip() else ""
    return PdfPageText(
        page_number=page_number,
        text=normalized,
        line_count=normalized.count("\n") + 1 if normalized else 0,
    )


def _result_from_pages(*, pages: list[PdfPageText], method: str, warnings: list[str] | None = None) -> PdfExtractionResult:
    text = normalize_import_text(_format_pages(pages))
    return PdfExtractionResult(text=text, pages=pages, method=method, warnings=warnings or [])


def extract_pdf_text_with_pymupdf(pdf_content: bytes) -> PdfExtractionResult:
    try:
        document = fitz.open(stream=pdf_content, filetype="pdf")
    except Exception as exc:
        raise PdfExtractionError("PDF content could not be opened") from exc

    pages = [_page_text(index + 1, page.get_text("text")) for index, page in enumerate(document)]
    text_pages = [page for page in pages if page.text]
    if not text_pages:
        raise PdfExtractionError("PDF text layer is empty")
    return _result_from_pages(pages=text_pages, method="pymupdf")


def _needs_layout_fallback(result: PdfExtractionResult) -> bool:
    if result.character_count < MIN_TEXT_CHARACTERS:
        return True
    price_hits = PRICE_PATTERN.findall(result.text)
    return bool(price_hits) and "\n" not in result.text


def extract_pdf_text_with_pdfplumber(pdf_content: bytes) -> PdfExtractionResult:
    try:
        with pdfplumber.open(BytesIO(pdf_content)) as document:
            pages = [
                _page_text(
                    index + 1,
                    page.extract_text(layout=True, x_tolerance=2, y_tolerance=4) or "",
                )
                for index, page in enumerate(document.pages)
            ]
    except Exception as exc:
        raise PdfExtractionError("PDF layout text could not be extracted") from exc

    text_pages = [page for page in pages if page.text]
    if not text_pages:
        raise PdfExtractionError("PDF layout text is empty")
    return _result_from_pages(pages=text_pages, method="pdfplumber")


def _render_page_for_ocr(page: fitz.Page) -> Image.Image:
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def _ocr_pdf_with_tesseract(pdf_content: bytes) -> PdfExtractionResult:
    try:
        document = fitz.open(stream=pdf_content, filetype="pdf")
    except Exception as exc:
        raise PdfExtractionError("PDF content could not be opened for OCR") from exc

    if document.page_count > MAX_OCR_PAGES:
        raise PdfExtractionError(f"OCR fallback cannot process more than {MAX_OCR_PAGES} pages")

    pages: list[PdfPageText] = []
    for index, page in enumerate(document):
        image = _render_page_for_ocr(page)
        text = pytesseract.image_to_string(image, lang="ita+eng")
        page_text = _page_text(index + 1, text)
        if page_text.text:
            pages.append(page_text)

    if not pages:
        raise PdfExtractionError("OCR did not find extractable text")
    return _result_from_pages(pages=pages, method="tesseract-ocr", warnings=["PDF text layer was empty; OCR fallback used"])


def _ocr_pdf_with_ocrmypdf(pdf_content: bytes) -> PdfExtractionResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.pdf"
        output_path = Path(tmpdir) / "output.pdf"
        input_path.write_bytes(pdf_content)
        try:
            subprocess.run(
                [
                    "ocrmypdf",
                    "--skip-text",
                    "--language",
                    "ita+eng",
                    "--quiet",
                    str(input_path),
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                timeout=90,
            )
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            raise PdfExtractionError("OCRmyPDF fallback failed") from exc
        return extract_pdf_text_with_pymupdf(output_path.read_bytes())


def extract_pdf_text_with_ocr(pdf_content: bytes) -> PdfExtractionResult:
    try:
        result = _ocr_pdf_with_ocrmypdf(pdf_content)
        return PdfExtractionResult(
            text=result.text,
            pages=result.pages,
            method="ocrmypdf",
            warnings=["PDF text layer was empty; OCR fallback used"],
        )
    except PdfExtractionError:
        return _ocr_pdf_with_tesseract(pdf_content)


def extract_pdf_text(pdf_content: bytes) -> PdfExtractionResult:
    warnings: list[str] = []
    try:
        pymupdf_result = extract_pdf_text_with_pymupdf(pdf_content)
    except PdfExtractionError:
        return extract_pdf_text_with_ocr(pdf_content)

    if not _needs_layout_fallback(pymupdf_result):
        return pymupdf_result

    try:
        layout_result = extract_pdf_text_with_pdfplumber(pdf_content)
    except PdfExtractionError:
        warnings.append("Layout-aware PDF fallback was not available")
        return PdfExtractionResult(
            text=pymupdf_result.text,
            pages=pymupdf_result.pages,
            method=pymupdf_result.method,
            warnings=warnings,
        )

    if layout_result.character_count >= pymupdf_result.character_count:
        return layout_result
    return pymupdf_result
