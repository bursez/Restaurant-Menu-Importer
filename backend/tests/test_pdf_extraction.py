from __future__ import annotations

import json
from pathlib import Path

import fitz
from httpx import ASGITransport, AsyncClient
import pytest

from app.services import pdf_extraction
from app.services.pdf_extraction import (
    PdfExtractionError,
    PdfExtractionResult,
    PdfPageText,
    clean_repeated_pdf_chrome,
    extract_pdf_text,
    extract_pdf_text_with_pymupdf,
)
from app.services.url_fetching import FetchedUrl, is_pdf_response


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "pdf_reference_texts"


def _make_text_pdf(pages: list[str]) -> bytes:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text, fontsize=12)
    return document.tobytes()


def test_pdf_content_detection_uses_header_or_signature() -> None:
    assert is_pdf_response(
        FetchedUrl(
            requested_url="https://restaurant.example/menu",
            final_url="https://restaurant.example/menu",
            content=b"%PDF-1.7\n...",
            content_type=None,
            status_code=200,
            redirect_count=0,
        )
    )
    assert is_pdf_response(
        FetchedUrl(
            requested_url="https://restaurant.example/menu",
            final_url="https://restaurant.example/menu",
            content=b"not a pdf signature",
            content_type="application/pdf",
            status_code=200,
            redirect_count=0,
        )
    )


def test_pymupdf_extracts_page_aware_text() -> None:
    pdf = _make_text_pdf(["ANTIPASTI\nBruschetta 6,50", "PRIMI\nSpaghetti 12,00"])

    result = extract_pdf_text_with_pymupdf(pdf)

    assert result.method == "pymupdf"
    assert result.page_count == 2
    assert "[Page 1]" in result.text
    assert "[Page 2]" in result.text
    assert "Bruschetta 6,50" in result.text
    assert result.pages[0].page_number == 1
    assert result.pages[1].line_count >= 2


def test_pdfplumber_fallback_is_used_for_sparse_text(monkeypatch: pytest.MonkeyPatch) -> None:
    sparse = PdfExtractionResult(
        text="[Page 1]\n€ 12",
        pages=[PdfPageText(page_number=1, text="€ 12", line_count=1)],
        method="pymupdf",
    )
    layout = PdfExtractionResult(
        text="[Page 1]\nANTIPASTI\nBruschetta € 12",
        pages=[PdfPageText(page_number=1, text="ANTIPASTI\nBruschetta € 12", line_count=2)],
        method="pdfplumber",
    )

    monkeypatch.setattr(pdf_extraction, "extract_pdf_text_with_pymupdf", lambda _: sparse)
    monkeypatch.setattr(pdf_extraction, "extract_pdf_text_with_pdfplumber", lambda _: layout)

    result = extract_pdf_text(b"%PDF-1.7")

    assert result.method == "pdfplumber"
    assert "Bruschetta" in result.text


def test_ocr_fallback_is_used_for_empty_text_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_empty(_: bytes) -> PdfExtractionResult:
        raise PdfExtractionError("PDF text layer is empty")

    ocr = PdfExtractionResult(
        text="[Page 1]\nMargherita € 5,50",
        pages=[PdfPageText(page_number=1, text="Margherita € 5,50", line_count=1)],
        method="ocrmypdf",
        warnings=["PDF text layer was empty; OCR fallback used"],
    )

    monkeypatch.setattr(pdf_extraction, "extract_pdf_text_with_pymupdf", raise_empty)
    monkeypatch.setattr(pdf_extraction, "extract_pdf_text_with_ocr", lambda _: ocr)

    result = extract_pdf_text(b"%PDF-1.7")

    assert result.method == "ocrmypdf"
    assert "OCR fallback used" in result.warnings[0]


def test_repeated_header_footer_and_legend_cleanup() -> None:
    pages = [
        PdfPageText(page_number=1, text="Il Covo del Ribelle\nANTIPASTI\nTartare 16\nLegenda allergeni", line_count=4),
        PdfPageText(page_number=2, text="Il Covo del Ribelle\nPRIMI\nTagliatelle 15\nLegenda allergeni", line_count=4),
    ]

    cleaned, warnings = clean_repeated_pdf_chrome(pages)

    assert "ANTIPASTI" in cleaned[0].text
    assert "PRIMI" in cleaned[1].text
    assert "Il Covo del Ribelle" not in cleaned[0].text
    assert "Legenda allergeni" not in cleaned[1].text
    assert warnings


def test_reference_pdf_fixture_manifest_covers_required_menus() -> None:
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())

    assert {case["slug"] for case in manifest} == {
        "re_sale",
        "il_covo_del_ribelle",
        "love_menu",
        "nobu_milan",
        "pizzeria_da_michele",
    }
    for case in manifest:
        text = (FIXTURE_DIR / case["fixture"]).read_text()
        assert case["url"] in text
        assert len(text) > 80


@pytest.mark.asyncio
async def test_create_url_import_accepts_pdf_url(app, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_url(url: str) -> FetchedUrl:
        return FetchedUrl(
            requested_url=url,
            final_url="https://restaurant.example/menu.pdf",
            content=b"%PDF-1.7",
            content_type="application/pdf",
            status_code=200,
            redirect_count=0,
        )

    monkeypatch.setattr("app.services.imports.fetch_url", fake_fetch_url)
    monkeypatch.setattr(
        "app.services.imports.extract_pdf_text",
        lambda _: PdfExtractionResult(
            text="[Page 1]\nNobu Milan\nYellowtail 32",
            pages=[PdfPageText(page_number=1, text="Nobu Milan\nYellowtail 32", line_count=2)],
            method="pymupdf",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/imports/url", json={"url": "https://restaurant.example/menu.pdf"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["source_filename"] == "https://restaurant.example/menu.pdf"
    assert "Yellowtail 32" in payload["source_value"]
    assert payload["events"][2]["message"] == "PDF menu text extracted"
    assert payload["events"][2]["event_metadata"]["method"] == "pymupdf"
