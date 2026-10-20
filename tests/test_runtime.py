"""Process uptime must not depend on when the status module is first loaded."""

from __future__ import annotations

import runpy
import time
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest


@pytest.mark.parametrize("elapsed", [0.75, 3661.75, 90061.75])
def test_uptime_includes_time_before_first_import(monkeypatch, elapsed):
    started_at = 1_700_000_000.0
    monkeypatch.setattr(
        psutil, "Process", lambda: SimpleNamespace(create_time=lambda: started_at)
    )
    monkeypatch.setattr(time, "time", lambda: started_at + elapsed)
    runtime_path = Path(__file__).resolve().parents[1] / "shared" / "runtime.py"

    runtime = runpy.run_path(str(runtime_path))
    assert runtime["get_uptime_seconds"]() == int(elapsed)

    monkeypatch.setattr(time, "time", lambda: started_at + elapsed + 30)
    assert runtime["get_uptime_seconds"]() == int(elapsed) + 30
    reloaded = runpy.run_path(str(runtime_path))
    assert reloaded["get_uptime_seconds"]() == int(elapsed) + 30
