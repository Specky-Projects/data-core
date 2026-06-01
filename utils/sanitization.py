from __future__ import annotations

import unicodedata
from typing import Any


def sanitize_for_postgres(value: Any) -> Any:
    """Return a PostgreSQL-safe copy of a nested payload."""
    if isinstance(value, str):
        cleaned = value.replace("\x00", "")
        cleaned = cleaned.encode("utf-8", "replace").decode("utf-8")
        cleaned = "".join(
            char
            for char in cleaned
            if char == "\t" or char == "\n" or char == "\r" or unicodedata.category(char) != "Cc"
        )
        return cleaned.replace("\x00", "")
    if isinstance(value, bytes):
        return sanitize_for_postgres(value.decode("utf-8", "replace"))
    if isinstance(value, dict):
        return {sanitize_for_postgres(key): sanitize_for_postgres(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_for_postgres(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_for_postgres(item) for item in value)
    return value
