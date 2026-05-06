from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from app.services.url_security import UrlValidationError, validate_public_url


MAX_FETCH_BYTES = 2_000_000
MAX_REDIRECTS = 5
FETCH_TIMEOUT_SECONDS = 10.0
USER_AGENT = "RestaurantMenuImporter/0.1 (+https://github.com/bursez/Restaurant-Menu-Importer)"


class UrlFetchError(ValueError):
    pass


@dataclass(frozen=True)
class FetchedUrl:
    requested_url: str
    final_url: str
    content: bytes
    content_type: str | None
    status_code: int
    redirect_count: int


def _content_type_without_parameters(value: str | None) -> str | None:
    if value is None:
        return None
    return value.split(";", maxsplit=1)[0].strip().lower() or None


async def fetch_url(url: str) -> FetchedUrl:
    requested_url = await validate_public_url(url)
    current_url = requested_url
    redirect_count = 0

    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(FETCH_TIMEOUT_SECONDS),
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,text/plain;q=0.9,*/*;q=0.8"},
    ) as client:
        while True:
            try:
                response = await client.get(current_url)
            except httpx.TimeoutException as exc:
                raise UrlFetchError("URL fetch timed out") from exc
            except httpx.HTTPError as exc:
                raise UrlFetchError("URL could not be fetched") from exc

            if response.is_redirect:
                redirect_count += 1
                if redirect_count > MAX_REDIRECTS:
                    raise UrlFetchError("URL redirected too many times")
                location = response.headers.get("Location")
                if not location:
                    raise UrlFetchError("URL redirect did not include a destination")
                current_url = await validate_public_url(urljoin(str(response.url), location))
                continue

            if response.status_code >= 400:
                raise UrlFetchError(f"URL returned HTTP {response.status_code}")

            content = response.content
            if len(content) > MAX_FETCH_BYTES:
                raise UrlFetchError(f"URL response cannot exceed {MAX_FETCH_BYTES} bytes")

            return FetchedUrl(
                requested_url=requested_url,
                final_url=str(response.url),
                content=content,
                content_type=_content_type_without_parameters(response.headers.get("Content-Type")),
                status_code=response.status_code,
                redirect_count=redirect_count,
            )


def is_html_response(fetched_url: FetchedUrl) -> bool:
    if fetched_url.content_type in {"text/html", "application/xhtml+xml"}:
        return True
    prefix = fetched_url.content[:200].lstrip().lower()
    return prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html")


def is_pdf_response(fetched_url: FetchedUrl) -> bool:
    if fetched_url.content_type == "application/pdf":
        return True
    return fetched_url.content.startswith(b"%PDF-")
