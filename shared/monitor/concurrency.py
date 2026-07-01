"""Bounded concurrency helpers for batch monitor checks and API fan-out."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")

DEFAULT_BATCH_CONCURRENCY = 3
MAX_BATCH_CONCURRENCY = 10


def _effective_limit(limit: int) -> int:
    if limit <= 0:
        return 1
    return min(limit, MAX_BATCH_CONCURRENCY)


async def run_with_concurrency(
    items: Sequence[T],
    worker: Callable[[T], Awaitable[R]],
    *,
    limit: int = DEFAULT_BATCH_CONCURRENCY,
) -> list[R | BaseException]:
    """Run *worker* over *items* with at most *limit* concurrent tasks.

    Results are returned in the same order as *items*. Exceptions from
    individual workers are captured as values instead of propagating.
    """
    if not items:
        return []

    sem = asyncio.Semaphore(_effective_limit(limit))

    async def _limited(item: T) -> R | BaseException:
        async with sem:
            try:
                return await worker(item)
            except asyncio.CancelledError:
                raise
            except BaseException as exc:
                return exc

    return list(await asyncio.gather(*(_limited(item) for item in items)))
