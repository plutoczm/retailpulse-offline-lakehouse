from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    """Per-process sliding-window limiter for protecting the LLM endpoint."""

    def __init__(self, limit_per_minute: int) -> None:
        self.limit = max(limit_per_minute, 0)
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, now: float | None = None) -> RateLimitDecision:
        if self.limit == 0:
            return RateLimitDecision(True, 2**31 - 1, 0)

        current = monotonic() if now is None else now
        cutoff = current - 60.0
        with self._lock:
            window = self._requests[key]
            while window and window[0] <= cutoff:
                window.popleft()

            if len(window) >= self.limit:
                retry_after = max(1, int(60.0 - (current - window[0])) + 1)
                return RateLimitDecision(False, 0, retry_after)

            window.append(current)
            return RateLimitDecision(True, self.limit - len(window), 0)
