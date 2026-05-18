from __future__ import annotations

import asyncio
import time

import pytest

from aquadx.utils.ratelimit import TokenBucket


@pytest.mark.asyncio
async def test_token_bucket_paces_calls() -> None:
    bucket = TokenBucket(rate=20.0)  # 20 RPS
    start = time.monotonic()
    for _ in range(25):  # capacity 20, so last 5 should wait ~0.25s
        await bucket.acquire()
    elapsed = time.monotonic() - start
    assert 0.2 <= elapsed < 1.5


@pytest.mark.asyncio
async def test_token_bucket_rejects_too_many_tokens() -> None:
    bucket = TokenBucket(rate=10.0)
    with pytest.raises(ValueError):
        await bucket.acquire(tokens=1000)


@pytest.mark.asyncio
async def test_token_bucket_concurrent_safe() -> None:
    bucket = TokenBucket(rate=50.0)
    await asyncio.gather(*[bucket.acquire() for _ in range(30)])


def test_invalid_rate_rejected() -> None:
    with pytest.raises(ValueError):
        TokenBucket(rate=0)
