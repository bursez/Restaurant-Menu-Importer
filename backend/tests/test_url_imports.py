from __future__ import annotations

import socket
import time

import httpx
from httpx import ASGITransport, AsyncClient
import pytest

from app.services import url_fetching
from app.core.config import Settings
from app.services.html_extraction import discover_pdf_links, extract_html_text
from app.services.url_fetching import FetchedUrl, fetch_url, is_html_response
from app.services.url_security import UrlValidationError, validate_public_url, validate_url_format


def test_validate_url_format_rejects_private_hosts() -> None:
    for url in (
        "http://localhost/menu",
        "http://127.0.0.1/menu",
        "http://10.0.0.5/menu",
        "http://169.254.169.254/latest/meta-data",
        "ftp://example.com/menu",
        "https://user:pass@example.com/menu",
    ):
        with pytest.raises(UrlValidationError):
            validate_url_format(url)


@pytest.mark.asyncio
async def test_validate_public_url_rejects_private_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.10", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(UrlValidationError, match="Private or internal URLs"):
        await validate_public_url("https://restaurant.example/menu")


@pytest.mark.asyncio
async def test_fetch_url_handles_redirects_and_content_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_validate_public_url(url: str) -> str:
        return url

    transport = httpx.MockTransport(
        lambda request: (
            httpx.Response(
                302,
                headers={"Location": "https://restaurant.example/menu"},
            )
            if str(request.url) == "https://restaurant.example"
            else httpx.Response(
                200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                content=b"<html><body>Menu</body></html>",
            )
        ),
    )

    class MockAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(transport=transport, *args, **kwargs)

    monkeypatch.setattr(url_fetching, "validate_public_url", fake_validate_public_url)
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    fetched_url = await fetch_url("https://restaurant.example")

    assert fetched_url == FetchedUrl(
        requested_url="https://restaurant.example",
        final_url="https://restaurant.example/menu",
        content=b"<html><body>Menu</body></html>",
        content_type="text/html",
        status_code=200,
        redirect_count=1,
    )
    assert is_html_response(fetched_url)


def test_extract_html_text_and_pdf_links() -> None:
    html = b"""
    <html>
      <head><title>Trattoria Demo</title><script>ignored()</script></head>
      <body>
        <nav>Navigation</nav>
        <main>
          <h1>Menu</h1>
          <p>Margherita&nbsp;7,50</p>
          <a href="/files/menu.pdf">Download menu</a>
        </main>
      </body>
    </html>
    """

    extraction = extract_html_text(html)
    assert "Margherita 7,50" in extraction.text
    assert "ignored" not in extraction.text
    assert discover_pdf_links(html, base_url="https://restaurant.example/menu") == [
        "https://restaurant.example/files/menu.pdf"
    ]


@pytest.mark.asyncio
async def test_create_url_import_extracts_html_and_records_pdf_links(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_url(url: str) -> FetchedUrl:
        return FetchedUrl(
            requested_url=url,
            final_url="https://restaurant.example/menu",
            content=b"""
            <html>
              <head><title>Restaurant Demo</title></head>
              <body>
                <main>
                  <h1>Lunch Menu</h1>
                  <p>Bruschetta 6,50</p>
                  <a href="/menu.pdf">PDF menu</a>
                </main>
              </body>
            </html>
            """,
            content_type="text/html",
            status_code=200,
            redirect_count=0,
        )

    monkeypatch.setattr("app.services.imports.fetch_url", fake_fetch_url)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/imports/url", json={"url": "https://restaurant.example/menu"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["input_type"] == "url"
    assert payload["source_filename"] == "https://restaurant.example/menu"
    assert "Bruschetta 6,50" in payload["source_value"]
    assert payload["status"] == "succeeded"
    assert [event["stage"] for event in payload["events"]] == [
        "created",
        "fetch",
        "extract",
        "ai_extraction",
        "ai_extraction",
    ]
    assert payload["events"][2]["event_metadata"]["pdf_links"] == ["https://restaurant.example/menu.pdf"]
    assert payload["extracted_menu"]["canonical_json"]["source"]["type"] == "url"


@pytest.mark.asyncio
async def test_create_url_import_rejects_internal_url(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/imports/url", json={"url": "http://127.0.0.1/menu"})

    assert response.status_code == 422
    assert response.json() == {"detail": "Private or internal URLs are not allowed"}


@pytest.mark.asyncio
async def test_create_url_import_times_out_slow_extraction(app, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_url(url: str) -> FetchedUrl:
        return FetchedUrl(
            requested_url=url,
            final_url=url,
            content=b"<html><body>Menu</body></html>",
            content_type="text/html",
            status_code=200,
            redirect_count=0,
        )

    def slow_extract_source(fetched_url: FetchedUrl):
        time.sleep(0.05)
        return None

    monkeypatch.setattr("app.services.imports.fetch_url", fake_fetch_url)
    monkeypatch.setattr("app.services.imports._extract_fetched_url_source_sync", slow_extract_source)
    monkeypatch.setattr(
        "app.services.imports.get_settings",
        lambda: Settings(gemini_use_fake=True, url_extraction_timeout_seconds=0.01),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/imports/url", json={"url": "https://restaurant.example/menu"})

    assert response.status_code == 422
    assert response.json() == {"detail": "URL extraction timed out"}
