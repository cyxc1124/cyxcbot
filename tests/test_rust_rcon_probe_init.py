"""Tests for rust_rcon_probe ORM init ordering."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PROBE_PATH = _ROOT / "scripts" / "rust_rcon_probe.py"


def _load_probe_module():
    spec = importlib.util.spec_from_file_location("rust_rcon_probe", _PROBE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_init_orm_sync_rejects_running_event_loop() -> None:
    probe = _load_probe_module()

    async def _inside_loop() -> None:
        with pytest.raises(RuntimeError, match="before asyncio.run"):
            probe._init_orm_sync()

    asyncio.run(_inside_loop())
