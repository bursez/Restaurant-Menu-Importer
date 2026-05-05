from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from readability import Document

from app.services.text_imports import normalize_import_text


class HtmlExtractionError(ValueError):
    pass


@dataclass(frozen=True)
class HtmlExtractionResult:
    text: str
    title: str | None


def _decode_html(content: bytes) -> str:
    for encoding in ("utf-8", "windows-1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _soup_to_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer", "form"]):
        tag.decompose()

    for tag in soup.find_all(["br", "p", "li", "tr", "h1", "h2", "h3", "h4", "section", "article"]):
        tag.append("\n")

    return soup.get_text("\n")


def extract_html_text(content: bytes) -> HtmlExtractionResult:
    html = _decode_html(content)
    document = Document(html)
    title = document.short_title().strip() or None
    summary_html = document.summary(html_partial=True)
    summary_soup = BeautifulSoup(summary_html, "lxml")
    extracted_text = _soup_to_text(summary_soup)

    try:
        normalized_text = normalize_import_text(extracted_text)
    except ValueError:
        fallback_soup = BeautifulSoup(html, "lxml")
        try:
            normalized_text = normalize_import_text(_soup_to_text(fallback_soup))
        except ValueError as exc:
            raise HtmlExtractionError("HTML page did not contain readable menu text") from exc

    return HtmlExtractionResult(text=normalized_text, title=title)


def discover_pdf_links(content: bytes, *, base_url: str) -> list[str]:
    html = _decode_html(content)
    soup = BeautifulSoup(html, "lxml")
    discovered_links: list[str] = []
    seen_links: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        label = anchor.get_text(" ", strip=True).lower()
        absolute_url = urljoin(base_url, href)
        lower_url = absolute_url.lower()
        if ".pdf" not in lower_url and "menu" not in label and "menù" not in label and "carta" not in label:
            continue
        if ".pdf" not in lower_url:
            continue
        if absolute_url in seen_links:
            continue
        seen_links.add(absolute_url)
        discovered_links.append(absolute_url)

    return discovered_links
