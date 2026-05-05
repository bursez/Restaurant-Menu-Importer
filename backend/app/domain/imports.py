from enum import StrEnum


class ImportInputType(StrEnum):
    TEXT = "text"
    URL = "url"
    FILE = "file"


class ImportStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ValidationStatus(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
