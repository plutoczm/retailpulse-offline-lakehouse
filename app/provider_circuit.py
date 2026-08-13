from __future__ import annotations
from threading import Lock
from time import monotonic

class CircuitBreaker:
    def __init__(self, threshold: int = 3, cooldown_seconds: float = 30.0) -> None:
        self.threshold=max(threshold,1); self.cooldown=max(cooldown_seconds,0.0)
        self.failures=0; self.opened_at: float|None=None; self.trial=False; self.lock=Lock()

    def allow(self, now: float|None=None) -> bool:
        current=monotonic() if now is None else now
        with self.lock:
            if self.opened_at is None: return True
            if current-self.opened_at < self.cooldown or self.trial: return False
            self.trial=True; return True

    def success(self) -> None:
        with self.lock:
            self.failures=0; self.opened_at=None; self.trial=False

    def failure(self, now: float|None=None) -> None:
        current=monotonic() if now is None else now
        with self.lock:
            self.failures+=1
            if self.trial or self.failures>=self.threshold:
                self.opened_at=current; self.trial=False
