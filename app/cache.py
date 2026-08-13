from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Generic, Hashable, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class ResponseCache(Generic[T]):
    """Thread-safe TTL/LRU cache keyed by the metrics data version."""

    def __init__(self, ttl_seconds: float = 60.0, max_entries: int = 256) -> None:
        self.ttl_seconds = max(ttl_seconds, 0.0)
        self.max_entries = max(max_entries, 1)
        self._items: OrderedDict[Hashable, _CacheEntry[T]] = OrderedDict()
        self._lock = Lock()

    @property
    def enabled(self) -> bool:
        return self.ttl_seconds > 0

    def get(self, key: Hashable, now: float | None = None) -> T | None:
        if not self.enabled:
            return None
        current = monotonic() if now is None else now
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            if entry.expires_at <= current:
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return entry.value

    def set(self, key: Hashable, value: T, now: float | None = None) -> None:
        if not self.enabled:
            return
        current = monotonic() if now is None else now
        with self._lock:
            self._items[key] = _CacheEntry(
                value=value,
                expires_at=current + self.ttl_seconds,
            )
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)
