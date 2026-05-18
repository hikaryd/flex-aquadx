from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    """Асинхронный rate-лимитер по схеме token bucket. Сглаженный темп с допуском всплесков.

    rate = токенов в секунду; capacity по умолчанию равна rate (запас на 1 секунду всплеска).
    """

    rate: float
    capacity: float | None = None

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise ValueError("rate must be positive")
        self._capacity = self.capacity if self.capacity is not None else self.rate
        self._tokens = self._capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        if tokens > self._capacity:
            raise ValueError("requested tokens exceeds capacity")
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._updated
                self._updated = now
                self._tokens = min(self._capacity, self._tokens + elapsed * self.rate)
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                wait = deficit / self.rate
                await asyncio.sleep(wait)
