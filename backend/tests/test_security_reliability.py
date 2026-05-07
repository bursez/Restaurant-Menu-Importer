from __future__ import annotations

from httpx import ASGITransport, AsyncClient
import pytest

from app.core.config import Settings
from app.core.errors import sanitize_error_message
from app.main import create_app


@pytest.mark.asyncio
async def test_request_id_header_is_preserved(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health", headers={"X-Request-ID": "test-request-123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-123"


@pytest.mark.asyncio
async def test_rate_limit_hook_can_be_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(
            gemini_use_fake=True,
            rate_limit_enabled=True,
            rate_limit_requests=1,
            rate_limit_window_seconds=60,
        ),
    )
    app = create_app()
    transport = ASGITransport(app=app, client=("203.0.113.10", 1234))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        first_response = await client.get("/api/health")
        second_response = await client.get("/api/health")

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert second_response.json() == {"detail": "Too many requests"}
    assert "retry-after" in second_response.headers
    assert "x-request-id" in second_response.headers


def test_sanitize_error_message_redacts_sensitive_details() -> None:
    message = "Gemini failed: api_key=AIzaSyVerySecretValue and /tmp/private/menu.pdf"

    sanitized = sanitize_error_message(message)

    assert "AIzaSyVerySecretValue" not in sanitized
    assert "/tmp/private/menu.pdf" not in sanitized
    assert "<local-path>" in sanitized
    assert "api_key=<redacted>" in sanitized
