"""Tests for shared.monitor.concurrency (issue #88)."""

from __future__ import annotations

import asyncio
import time

import pytest

from shared.monitor.concurrency import (
    DEFAULT_BATCH_CONCURRENCY,
    MAX_BATCH_CONCURRENCY,
    run_with_concurrency,
)


@pytest.mark.asyncio
async def test_run_with_concurrency_empty_items() -> None:
    async def identity(item: str) -> str:
        return item

    assert await run_with_concurrency([], identity) == []


@pytest.mark.asyncio
async def test_run_with_concurrency_preserves_order() -> None:
    async def worker(item: int) -> int:
        await asyncio.sleep(0.01 * (3 - item))
        return item * 10

    results = await run_with_concurrency([0, 1, 2], worker, limit=3)
    assert results == [0, 10, 20]


@pytest.mark.asyncio
async def test_run_with_concurrency_limits_in_flight() -> None:
    in_flight = 0
    peak = 0
    delay = 0.05

    async def worker(_item: int) -> bool:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(delay)
        in_flight -= 1
        return True

    items = list(range(10))
    started = time.monotonic()
    results = await run_with_concurrency(items, worker, limit=3)
    elapsed = time.monotonic() - started

    assert results == [True] * len(items)
    assert peak <= 3
    assert elapsed < len(items) * delay


@pytest.mark.asyncio
async def test_run_with_concurrency_isolates_failures() -> None:
    async def worker(item: str) -> str:
        if item == "bad":
            raise RuntimeError("boom")
        return item

    results = await run_with_concurrency(["ok", "bad", "fine"], worker, limit=3)
    assert results[0] == "ok"
    assert isinstance(results[1], RuntimeError)
    assert results[2] == "fine"


@pytest.mark.asyncio
async def test_run_with_concurrency_caps_limit() -> None:
    peak = 0
    in_flight = 0

    async def worker(_item: int) -> None:
        nonlocal peak, in_flight
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1

    await run_with_concurrency(list(range(8)), worker, limit=999)
    assert peak <= MAX_BATCH_CONCURRENCY


def test_default_batch_concurrency_is_three() -> None:
    assert DEFAULT_BATCH_CONCURRENCY == 3
