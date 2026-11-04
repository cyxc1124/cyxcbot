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

    def reserve(self, ip: str, username: str) -> tuple[int, float]:
        """同步占用一次尝试名额，返回 (需等待秒数, 占用时间戳)。

        检查与占用之间没有 await，并发请求不会同时越过上限；占用的名额按失败计，
        登录成功后由 release_success 退还。已被限制时不占用，等待秒数大于 0。
        """
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
        if wait > 0:
            return int(wait) + 1, now
        for bucket, key in ((self._ip, ip), (self._user, username)):
            if len(bucket) >= _MAX_KEYS and key not in bucket:
                bucket.pop(next(iter(bucket)))
            bucket[key].append(now)
        return 0, now

    def release_success(self, ip: str, username: str, stamp: float) -> None:
        """登录成功：退还来源地址的名额，并清空该用户名的计数。"""
        hits = self._ip.get(ip)
        if hits is not None:
            try:
                hits.remove(stamp)
            except ValueError:
                pass
            if not hits:
                del self._ip[ip]
        self._user.pop(username, None)


login_limiter = LoginLimiter()
