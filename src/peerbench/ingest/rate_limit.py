"""Token-bucket rate limiter, shared by the FDIC API client and the
FFIEC CDR ingester. PLAN.md spec: 5 req/s ceiling against the FDIC API.

Sync only — the rest of the pipeline is sync. Reusing this in async land
would need an asyncio-aware variant, which we don't need at Phase 1 scale.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class TokenBucket:
    """A simple token-bucket throttle.

    Tokens replenish at `rate_per_second` per second up to `capacity`.
    `acquire()` blocks (sleeps) until a token is available, then consumes one.
    Thread-safe so a future parallel ingest can share one bucket.
    """

    def __init__(
        self,
        rate_per_second: float,
        capacity: int | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if rate_per_second <= 0:
            msg = f"rate_per_second must be positive, got {rate_per_second}"
            raise ValueError(msg)
        self._rate = rate_per_second
        self._capacity = float(capacity if capacity is not None else max(1, int(rate_per_second)))
        self._tokens = self._capacity
        self._last_refill = clock()
        self._lock = threading.Lock()
        self._clock = clock
        self._sleep = sleep

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = self._clock()
                elapsed = now - self._last_refill
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                deficit = 1.0 - self._tokens
                wait = deficit / self._rate
            self._sleep(wait)
