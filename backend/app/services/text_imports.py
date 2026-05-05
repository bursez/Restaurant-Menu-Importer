from __future__ import annotations

import re


MAX_IMPORT_TEXT_LENGTH = 200_000
SUPPORTED_TEXT_FILE_EXTENSIONS = {".md", ".txt"}

_HORIZONTAL_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
_BLANK_LINE_RE = re.compile(r"\n{3,}")


class TextImportValidationError(ValueError):
    pass


def normalize_import_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\ufeff", "")
    normalized = normalized.replace("\u00a0", " ")
    normalized = normalized.replace("•", "-")
    normalized = "\n".join(_HORIZONTAL_WHITESPACE_RE.sub(" ", line).strip() for line in normalized.split("\n"))
    normalized = _BLANK_LINE_RE.sub("\n\n", normalized).strip()

    if not normalized:
        raise TextImportValidationError("Import text cannot be empty")
    if len(normalized) > MAX_IMPORT_TEXT_LENGTH:
        raise TextImportValidationError(f"Import text cannot exceed {MAX_IMPORT_TEXT_LENGTH} characters")

    return normalized


def validate_text_filename(filename: str | None) -> str:
    if not filename:
        raise TextImportValidationError("Uploaded file must include a filename")

    normalized_filename = filename.rsplit("/", maxsplit=1)[-1].rsplit("\\", maxsplit=1)[-1]
    lower_filename = normalized_filename.lower()
    if not any(lower_filename.endswith(extension) for extension in SUPPORTED_TEXT_FILE_EXTENSIONS):
        raise TextImportValidationError("Only .txt and .md menu files are supported")

    return normalized_filename
