from __future__ import annotations

from decimal import Decimal
from typing import TypedDict


class EvaluationCaseSeed(TypedDict):
    slug: str
    name: str
    source_url: str
    case_set: str
    source_fixture_path: str | None
    expected_fixture_path: str | None
    actual_fixture_path: str | None
    qualitative_score: Decimal | None
    strengths: str
    weaknesses: str
    notes: str


EVALUATION_CASES: list[EvaluationCaseSeed] = [
    {
        "slug": "re-sale",
        "name": "Re Sale",
        "source_url": "https://www.resaleristorante.it/menu.pdf",
        "case_set": "required",
        "source_fixture_path": "tests/fixtures/pdf_reference_texts/re_sale.txt",
        "expected_fixture_path": "app/evaluation_fixtures/expected/re_sale.json",
        "actual_fixture_path": "app/evaluation_fixtures/actual/re_sale.json",
        "qualitative_score": Decimal("8.00"),
        "strengths": "Text-layer PDF keeps dish names and most prices readable.",
        "weaknesses": "Column spacing can separate descriptions from prices.",
        "notes": "Strong baseline for page-order and price alignment checks.",
    },
    {
        "slug": "il-covo-del-ribelle",
        "name": "Il Covo del Ribelle",
        "source_url": "https://www.ilcovodelribelle.it/menu.pdf",
        "case_set": "required",
        "source_fixture_path": "tests/fixtures/pdf_reference_texts/il_covo_del_ribelle.txt",
        "expected_fixture_path": "app/evaluation_fixtures/expected/il_covo_del_ribelle.json",
        "actual_fixture_path": "app/evaluation_fixtures/actual/il_covo_del_ribelle.json",
        "qualitative_score": Decimal("7.20"),
        "strengths": "Long-form categories and tasting-menu sections are preserved.",
        "weaknesses": "Legends and repeated footer material can still look like menu text.",
        "notes": "Used to track resilience on long, noisy Italian PDFs.",
    },
    {
        "slug": "love-menu",
        "name": "Love Menu",
        "source_url": "https://linktr.ee/lovemenu",
        "case_set": "required",
        "source_fixture_path": "tests/fixtures/pdf_reference_texts/love_menu.txt",
        "expected_fixture_path": "app/evaluation_fixtures/expected/love_menu.json",
        "actual_fixture_path": "app/evaluation_fixtures/actual/love_menu.json",
        "qualitative_score": Decimal("7.60"),
        "strengths": "Remote PDF source is handled independently from the host domain.",
        "weaknesses": "Compact item lists need careful category boundary detection.",
        "notes": "Covers CDN and indirect-hosted menu material.",
    },
    {
        "slug": "nobu-milan",
        "name": "Nobu Milan",
        "source_url": "https://www.noburestaurants.com/milan/menu.pdf",
        "case_set": "required",
        "source_fixture_path": "tests/fixtures/pdf_reference_texts/nobu_milan.txt",
        "expected_fixture_path": "app/evaluation_fixtures/expected/nobu_milan.json",
        "actual_fixture_path": "app/evaluation_fixtures/actual/nobu_milan.json",
        "qualitative_score": Decimal("8.40"),
        "strengths": "Bilingual names and descriptions are retained cleanly.",
        "weaknesses": "Roll variants with multiple prices need normalization review.",
        "notes": "Primary bilingual-language handling case.",
    },
    {
        "slug": "pizzeria-da-michele",
        "name": "Pizzeria Da Michele",
        "source_url": "https://www.damichele.net/menu.pdf",
        "case_set": "required",
        "source_fixture_path": "tests/fixtures/pdf_reference_texts/pizzeria_da_michele_ocr.txt",
        "expected_fixture_path": "app/evaluation_fixtures/expected/pizzeria_da_michele.json",
        "actual_fixture_path": "app/evaluation_fixtures/actual/pizzeria_da_michele.json",
        "qualitative_score": Decimal("6.80"),
        "strengths": "OCR fallback recovers enough text for core pizza entries.",
        "weaknesses": "Image-only scans lose some formatting and can miss accents.",
        "notes": "Required OCR regression case.",
    },
    {
        "slug": "osteria-francescana",
        "name": "Osteria Francescana",
        "source_url": "https://osteriafrancescana.it/menu",
        "case_set": "additional",
        "source_fixture_path": None,
        "expected_fixture_path": None,
        "actual_fixture_path": "app/evaluation_fixtures/actual/osteria_francescana.json",
        "qualitative_score": Decimal("7.50"),
        "strengths": "Short tasting-menu structure is easy to validate.",
        "weaknesses": "Fixed-price tasting menus often omit per-dish prices.",
        "notes": "Qualitative case for chef-driven tasting menus.",
    },
    {
        "slug": "dishoom-covent-garden",
        "name": "Dishoom Covent Garden",
        "source_url": "https://www.dishoom.com/covent-garden/menu/",
        "case_set": "additional",
        "source_fixture_path": None,
        "expected_fixture_path": None,
        "actual_fixture_path": "app/evaluation_fixtures/actual/dishoom_covent_garden.json",
        "qualitative_score": Decimal("8.10"),
        "strengths": "HTML-style sections and allergen tags are cleanly separable.",
        "weaknesses": "Large menus can produce duplicate subsection headings.",
        "notes": "Qualitative case for public HTML menus.",
    },
    {
        "slug": "eleven-madison-park",
        "name": "Eleven Madison Park",
        "source_url": "https://www.elevenmadisonpark.com/menu/",
        "case_set": "additional",
        "source_fixture_path": None,
        "expected_fixture_path": None,
        "actual_fixture_path": "app/evaluation_fixtures/actual/eleven_madison_park.json",
        "qualitative_score": Decimal("7.00"),
        "strengths": "Plant-based tasting menu language is preserved.",
        "weaknesses": "No per-item prices means price coverage is intentionally low.",
        "notes": "Qualitative case for menu language without item prices.",
    },
    {
        "slug": "gramercy-tavern",
        "name": "Gramercy Tavern",
        "source_url": "https://www.gramercytavern.com/menus/",
        "case_set": "additional",
        "source_fixture_path": None,
        "expected_fixture_path": None,
        "actual_fixture_path": "app/evaluation_fixtures/actual/gramercy_tavern.json",
        "qualitative_score": Decimal("8.30"),
        "strengths": "Seasonal categories and prices are represented consistently.",
        "weaknesses": "Multiple dining-room menus require source selection notes.",
        "notes": "Qualitative case for category coverage and price density.",
    },
    {
        "slug": "st-john",
        "name": "St. John",
        "source_url": "https://stjohnrestaurant.com/a/menus/",
        "case_set": "additional",
        "source_fixture_path": None,
        "expected_fixture_path": None,
        "actual_fixture_path": "app/evaluation_fixtures/actual/st_john.json",
        "qualitative_score": Decimal("7.80"),
        "strengths": "Concise dish names and changing prices are easy to scan.",
        "weaknesses": "Daily menu rotation makes live comparison manual-only.",
        "notes": "Qualitative case for frequently changing public menus.",
    },
]
