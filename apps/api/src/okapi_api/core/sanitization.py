"""Input sanitization and validation utilities (Phase 09)."""

import re

# Bidi control characters and null bytes
DISALLOWED_CONTROL_CHARS = re.compile(r"[\x00\u200e\u200f\u202a-\u202e\u2066-\u2069]")
VALID_FIELD_KEY_PATTERN = re.compile(r"^[a-z0-9_]+(?:\.[a-z0-9_]+)*$")


def sanitize_text(text: str) -> str:
    """Strip null bytes, bidi unicode overrides, and normalize input strings."""
    if not text:
        return ""
    # Remove dangerous control chars
    cleaned = DISALLOWED_CONTROL_CHARS.sub("", text)
    return cleaned.strip()


def validate_field_key(key: str) -> bool:
    """Validate that field_key follows clean dot-separated alphanumeric conventions."""
    return bool(VALID_FIELD_KEY_PATTERN.match(key.strip().lower()))
