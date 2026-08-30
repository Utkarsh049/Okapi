"""Unit tests for security headers, payload limit middleware, and sanitization (Phase 09)."""

from starlette.testclient import TestClient

from okapi_api.core.sanitization import sanitize_text, validate_field_key
from okapi_api.main import app


def test_security_headers_present_on_responses() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200

    headers = resp.headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-XSS-Protection"] == "1; mode=block"
    assert "Strict-Transport-Security" in headers
    assert headers["Content-Security-Policy"] == "default-src 'self'"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_payload_size_limit_rejection() -> None:
    client = TestClient(app)
    # Simulate an oversized request with header exceeding 5MB
    oversized_length = str(6 * 1024 * 1024)
    resp = client.post(
        "/api/v1/documents",
        content=b"{}",
        headers={"Content-Type": "application/json", "Content-Length": oversized_length},
    )
    assert resp.status_code == 413
    assert "payload too large" in resp.json()["detail"].lower()


def test_sanitization_strips_null_bytes_and_bidi_controls() -> None:
    malicious = "Clinical\x00 Note\u202e [HIDDEN]\u200e"
    cleaned = sanitize_text(malicious)
    assert "\x00" not in cleaned
    assert "\u202e" not in cleaned
    assert "\u200e" not in cleaned
    assert cleaned == "Clinical Note [HIDDEN]"


def test_validate_field_key() -> None:
    assert validate_field_key("patient.diagnosis") is True
    assert validate_field_key("vitals.bp_systolic") is True
    assert validate_field_key("study.cohort_size_2026") is True

    assert validate_field_key("../etc/passwd") is False
    assert validate_field_key("<script>") is False
    assert validate_field_key("patient.diagnosis; DROP TABLE") is False
