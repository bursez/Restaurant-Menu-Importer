from __future__ import annotations

import re


_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s,;]+"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
]
_URL_CREDENTIAL_PATTERN = re.compile(r"(https?://)[^:/\s]+:[^@\s]+@")
_LOCAL_PATH_PATTERN = re.compile(r"(?<!\w)(/[\w .@%+=:,~/-]{8,})")
_MAX_ERROR_LENGTH = 240


def sanitize_error_message(message: str | None, *, fallback: str = "Import failed") -> str:
    if not message:
        return fallback

    sanitized = message.replace("\r", " ").replace("\n", " ")
    sanitized = _URL_CREDENTIAL_PATTERN.sub(r"\1", sanitized)
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(_redact_secret_match, sanitized)
    sanitized = _LOCAL_PATH_PATTERN.sub("<local-path>", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    if len(sanitized) > _MAX_ERROR_LENGTH:
        return f"{sanitized[: _MAX_ERROR_LENGTH - 1].rstrip()}..."
    return sanitized or fallback


def _redact_secret_match(match: re.Match[str]) -> str:
    matched_text = match.group(0)
    if "=" not in matched_text and ":" not in matched_text:
        return "<redacted>"
    secret_name = matched_text.split("=", maxsplit=1)[0].split(":", maxsplit=1)[0]
    return f"{secret_name}=<redacted>"
