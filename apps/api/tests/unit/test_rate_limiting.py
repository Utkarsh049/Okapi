import pytest
from fastapi import HTTPException
from starlette.requests import Request

from okapi_api.core.rate_limit import RateLimiter, TokenBucketRateLimiter


def test_token_bucket_sliding_window_throttling() -> None:
    limiter = TokenBucketRateLimiter()
    key = "test_client_ip"

    # First 3 requests in a 1-second window are allowed
    for _ in range(3):
        allowed, retry_after = limiter.check_rate_limit(key=key, max_requests=3, window_seconds=1.0)
        assert allowed is True
        assert retry_after == 0

    # 4th request must be rejected
    allowed, retry_after = limiter.check_rate_limit(key=key, max_requests=3, window_seconds=1.0)
    assert allowed is False
    assert retry_after >= 1


@pytest.mark.asyncio
async def test_rate_limiter_dependency_raises_429() -> None:
    limiter = TokenBucketRateLimiter()
    rate_limit_dep = RateLimiter(max_requests=2, window_seconds=10.0, limiter=limiter)

    scope = {
        "type": "http",
        "client": ("127.0.0.1", 50000),
        "headers": [(b"authorization", b"Bearer test-token")],
    }
    req = Request(scope)

    # First 2 calls pass
    await rate_limit_dep(req)
    await rate_limit_dep(req)

    # 3rd call raises 429
    with pytest.raises(HTTPException) as exc_info:
        await rate_limit_dep(req)

    assert exc_info.value.status_code == 429
    assert "rate limit exceeded" in exc_info.value.detail.lower()
    assert "Retry-After" in exc_info.value.headers
