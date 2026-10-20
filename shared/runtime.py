"""Process runtime helpers."""

from __future__ import annotations

import time

import psutil

STARTED_AT = psutil.Process().create_time()


def get_uptime_seconds() -> int:
    return int(time.time() - STARTED_AT)
