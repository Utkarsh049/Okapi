"""Token revocation store for blacklisting revoked JWTs (e.g. on logout).

Thread-safe in-memory store with automatic expired-entry eviction.
Can be upgraded to a Redis-backed store post-prototype.
"""

import threading
import time
from datetime import datetime
from typing import Protocol


class TokenRevocationStore(Protocol):
    def revoke(self, jti: str, expires_at: float | int | datetime) -> None: ...
    def is_revoked(self, jti: str) -> bool: ...


class InMemoryTokenRevocationStore:
    """Thread-safe in-memory store holding revoked token IDs (jti) until expiration."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._revoked: dict[str, float] = {}

    def _cleanup_expired(self, now: float) -> None:
        """Evict tokens whose expiration timestamp has already passed."""
        expired = [jti for jti, exp in self._revoked.items() if exp <= now]
        for jti in expired:
            del self._revoked[jti]

    def revoke(self, jti: str, expires_at: float | int | datetime) -> None:
        if isinstance(expires_at, datetime):
            exp_timestamp = expires_at.timestamp()
        else:
            exp_timestamp = float(expires_at)

        now = time.time()
        with self._lock:
            self._cleanup_expired(now)
            if exp_timestamp > now:
                self._revoked[jti] = exp_timestamp

    def is_revoked(self, jti: str) -> bool:
        now = time.time()
        with self._lock:
            exp = self._revoked.get(jti)
            if exp is None:
                return False
            if exp <= now:
                del self._revoked[jti]
                return False
            return True


_global_token_store = InMemoryTokenRevocationStore()


def get_token_revocation_store() -> InMemoryTokenRevocationStore:
    """Return the singleton in-memory token revocation store."""
    return _global_token_store
