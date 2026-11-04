"""In-memory failed-login limiter (per client address and per username)."""

from __future__ import annotations

import time
from collections import defaultdict, deque

WINDOW_SECONDS = 15 * 60
MAX_FAILURES_PER_IP = 20
MAX_FAILURES_PER_USERNAME = 10
# 防止伪造大量用户名撑爆内存；超出时丢弃最旧的键。
_MAX_KEYS = 10_000


class LoginLimiter:
    # shortcut: 进程内计数，多副本部署时各自计数；上限按副本数放大。
    def __init__(self) -> None:
        self._ip: dict[str, deque[float]] = defaultdict(deque)
        self._user: dict[str, deque[float]] = defaultdict(deque)

    @staticmethod
    def _prune(bucket: dict[str, deque[float]], key: str, now: float) -> deque[float]:
        hits = bucket[key]
        while hits and now - hits[0] >= WINDOW_SECONDS:
            hits.popleft()
        if not hits:
            del bucket[key]
            return bucket[key]
        return hits

    def retry_after(self, ip: str, username: str) -> int:
        """已被限制时返回需等待的秒数，否则 0。"""
        now = time.monotonic()
        wait = 0.0
        for bucket, key, limit in (
            (self._ip, ip, MAX_FAILURES_PER_IP),
            (self._user, username, MAX_FAILURES_PER_USERNAME),
        ):
            if key not in bucket:
                continue
            hits = self._prune(bucket, key, now)
            if len(hits) >= limit:
                wait = max(wait, WINDOW_SECONDS - (now - hits[0]))
        return int(wait) + 1 if wait > 0 else 0

    def record_failure(self, ip: str, username: str) -> None:
        now = time.monotonic()
        for bucket, key in ((self._ip, ip), (self._user, username)):
            if len(bucket) >= _MAX_KEYS and key not in bucket:
                bucket.pop(next(iter(bucket)))
            bucket[key].append(now)

    def record_success(self, username: str) -> None:
        self._user.pop(username, None)


login_limiter = LoginLimiter()
