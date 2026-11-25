"""In-memory sliding-window rate limiter. Enough for a single backend process."""

import threading
from collections import deque


class SlidingWindowRateLimiter:
    """Allows at most `max_requests` per key within any `window_s` seconds.

    Time is passed in (monotonic seconds), so tests can control it.
    """

    def __init__(self, max_requests: int, window_s: float) -> None:
        self.max_requests = max_requests
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = {}
        self._last_sweep = 0.0
        # FastAPI runs sync endpoints in a thread pool.
        self._lock = threading.Lock()

    def allow(self, key: str, now: float) -> bool:
        with self._lock:
            self._sweep(now)
            hits = self._hits.setdefault(key, deque())
            self._drop_old(hits, now)
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True

    def _drop_old(self, hits: deque[float], now: float) -> None:
        while hits and hits[0] <= now - self.window_s:
            hits.popleft()

    def _sweep(self, now: float) -> None:
        # Forget visitors that have been quiet for a whole window, so memory does not grow.
        if now - self._last_sweep < self.window_s:
            return
        for key in list(self._hits):
            self._drop_old(self._hits[key], now)
            if not self._hits[key]:
                del self._hits[key]
        self._last_sweep = now
