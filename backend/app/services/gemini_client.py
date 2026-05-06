from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings


class GeminiError(Exception):
    pass


class GeminiConfigurationError(GeminiError):
    pass


class GeminiRequestError(GeminiError):
    pass


class GeminiResponseError(GeminiError):
    pass


@dataclass(frozen=True)
class GeminiRawResponse:
    payload: dict[str, Any]
    model: str


class GeminiAdapter(Protocol):
    model: str

    async def generate_structured_menu(
        self,
        *,
        prompt: str,
        response_schema: dict[str, Any],
    ) -> GeminiRawResponse:
        raise NotImplementedError


class HttpGeminiAdapter:
    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None) -> None:
        self.model = settings.gemini_model
        self._api_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        self._timeout = settings.gemini_request_timeout_seconds
        self._client = client

    async def generate_structured_menu(
        self,
        *,
        prompt: str,
        response_schema: dict[str, Any],
    ) -> GeminiRawResponse:
        if not self._api_key:
            raise GeminiConfigurationError("Gemini API key is not configured")

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json",
                "response_schema": response_schema,
            },
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        params = {"key": self._api_key}

        if self._client is not None:
            response = await self._client.post(url, params=params, json=payload, timeout=self._timeout)
            return self._parse_response(response)

        async with httpx.AsyncClient() as client:
            response = await client.post(url, params=params, json=payload, timeout=self._timeout)
            return self._parse_response(response)

    def _parse_response(self, response: httpx.Response) -> GeminiRawResponse:
        if response.status_code >= 400:
            raise GeminiRequestError(f"Gemini request failed with HTTP {response.status_code}")
        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise GeminiResponseError("Gemini returned a non-JSON response") from exc

        text = _extract_candidate_text(body)
        try:
            payload = json.loads(_strip_json_fence(text))
        except json.JSONDecodeError as exc:
            raise GeminiResponseError("Gemini returned invalid structured JSON") from exc
        if not isinstance(payload, dict):
            raise GeminiResponseError("Gemini structured output must be a JSON object")
        return GeminiRawResponse(payload=payload, model=self.model)


def _extract_candidate_text(body: dict[str, Any]) -> str:
    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise GeminiResponseError("Gemini response did not include candidates")
    content = candidates[0].get("content")
    if not isinstance(content, dict):
        raise GeminiResponseError("Gemini response did not include candidate content")
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise GeminiResponseError("Gemini response did not include content parts")
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            return part["text"]
    raise GeminiResponseError("Gemini response did not include text output")


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
