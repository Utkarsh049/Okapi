"""Token-bucket sliding-window rate limiter for sensitive API endpoints (Phase 09)."""

import hashlib
import math
import threading
import time

from fastapi import HTTPException, Request, status


class TokenBucketRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[str, list[float]] = {}

    def check_rate_limit(
        self, key: str, max_requests: int, window_seconds: float
    ) -> tuple[bool, int]:
        """Check if request is allowed under sliding window limit.

        Returns (allowed: bool, retry_after_seconds: int).
        """
        now = time.time()
        with self._lock:
            history = self._requests.get(key, [])
            # Evict timestamps outside current window
            cutoff = now - window_seconds
            valid_history = [t for t in history if t > cutoff]

            if len(valid_history) >= max_requests:
                self._requests[key] = valid_history
                oldest = valid_history[0]
                retry_after = max(1, math.ceil(window_seconds - (now - oldest)))
                return False, retry_after

            valid_history.append(now)
            self._requests[key] = valid_history
            return True, 0

    def reset(self) -> None:
        """Clear all rate limit state (useful in test suites)."""
        with self._lock:
            self._requests.clear()


# Global shared rate limiter instance
_global_rate_limiter = TokenBucketRateLimiter()


def get_global_rate_limiter() -> TokenBucketRateLimiter:
    return _global_rate_limiter


class RateLimiter:
    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: float = 60.0,
        limiter: TokenBucketRateLimiter | None = None,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.limiter = limiter or _global_rate_limiter

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown_client"
        auth_header = request.headers.get("authorization", "")
        # Hash the full auth header so distinct tokens actually produce distinct keys.
        # (A raw prefix doesn't work here: every JWT this app issues has an identical
        # ~36-char base64 header segment, since alg/typ never vary, so the first ~32
        # chars of any "Bearer <token>" string are the same for every user.)
        auth_fingerprint = (
            hashlib.sha256(auth_header.encode()).hexdigest()[:16] if auth_header else "anon"
        )
        key = f"{client_ip}:{auth_fingerprint}"

        allowed, retry_after = self.limiter.check_rate_limit(
            key=key,
            max_requests=self.max_requests,
            window_seconds=self.window_seconds,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too Many Requests: rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
