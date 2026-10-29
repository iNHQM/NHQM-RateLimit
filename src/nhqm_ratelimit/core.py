"""In-memory sliding-window rate limiter with monotonic time and a lock."""
from collections import deque
from dataclasses import dataclass
from math import ceil, isfinite
from threading import RLock
from time import monotonic
from typing import Deque, Dict, Optional


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: float
    reset_after: float


class RateLimitExceeded(Exception):
    """Raised by RateLimiter.require() when the key has exhausted its quota."""

    def __init__(self, result: RateLimitResult):
        self.result = result
        super().__init__(f"Rate limit exceeded; retry after {result.retry_after:.2f}s")


class RateLimiter:
    """Per-key sliding-window limiter for a single Python process.

    Every call to check() costs one request when allowed.
    Blocked requests are not counted.
    """

    def __init__(self, limit: int, window: float, *, max_keys: Optional[int] = None):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer")
        if isinstance(window, bool) or not isinstance(window, (int, float)) or not isfinite(window) or window <= 0:
            raise ValueError("window must be a positive finite number")
        if max_keys is not None and (isinstance(max_keys, bool) or not isinstance(max_keys, int) or max_keys <= 0):
            raise ValueError("max_keys must be a positive integer or None")
        self.limit = limit
        self.window = float(window)
        self.max_keys = max_keys
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = RLock()

    def _prune(self, key: str, now: float) -> Deque[float]:
        hits = self._hits.get(key)
        if hits is None:
            return deque()
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if not hits:
            del self._hits[key]
            return deque()
        return hits

    def check(self, key: str) -> RateLimitResult:
        """Check and consume one slot for a key, if available."""
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")
        with self._lock:
            now = monotonic()
            hits = self._prune(key, now)
            if len(hits) >= self.limit:
                wait = max(0.0, hits[0] + self.window - now)
                return RateLimitResult(False, self.limit, 0, wait, wait)
            if not hits and key not in self._hits:
                if self.max_keys is not None and len(self._hits) >= self.max_keys:
                    self.cleanup()
                    if len(self._hits) >= self.max_keys:
                        raise RuntimeError("maximum active keys reached; use a shared backend for large deployments")
                self._hits[key] = hits
            hits.append(now)
            remaining = self.limit - len(hits)
            reset = max(0.0, hits[0] + self.window - now)
            return RateLimitResult(True, self.limit, remaining, 0.0, reset)

    def require(self, key: str) -> RateLimitResult:
        """Like check(), but raises RateLimitExceeded if blocked."""
        result = self.check(key)
        if not result.allowed:
            raise RateLimitExceeded(result)
        return result

    def reset(self, key: str) -> None:
        """Forget a key's request history."""
        with self._lock:
            self._hits.pop(key, None)

    def cleanup(self) -> int:
        """Remove expired keys and return how many were removed."""
        with self._lock:
            now = monotonic()
            before = len(self._hits)
            for key in list(self._hits):
                self._prune(key, now)
            return before - len(self._hits)

    @property
    def active_keys(self) -> int:
        with self._lock:
            return len(self._hits)
