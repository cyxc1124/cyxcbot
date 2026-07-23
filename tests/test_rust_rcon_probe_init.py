"""Tests for rust_rcon_probe ORM init ordering."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

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


def test_is_giveto_command() -> None:
    probe = _load_probe_module()
    assert probe._is_giveto_command("giveto 76561198000000000 wood 1")
    assert probe._is_giveto_command("  GIVETO x y z")
    assert not probe._is_giveto_command("status")
    assert not probe._is_giveto_command("inventory.giveto player item 1")


def test_finish_rcon_success_skips_give_rejection_for_non_giveto() -> None:
    probe = _load_probe_module()
    assert probe._finish_rcon_success("status", "Couldn't find player") == 0
    assert probe._finish_rcon_success("giveto x y z", "Couldn't find player") == 1


def test_policy_ok_blocks_disabled_group_message() -> None:
    from shared.config.rust_rcon_policy import RustRconGroupPolicyRecord
    from shared.config.types import AppConfigSnapshot

    probe = _load_probe_module()
    snap = AppConfigSnapshot(
        message_group_restrict=True,
        message_enabled_group_ids=["999"],
        rust_rcon_group_policies={
            "123": RustRconGroupPolicyRecord(group_id="123", enabled=True),
        },
    )
    assert not probe._policy_ok(snap, group_id="123", user_id="1", private=False)


def test_policy_ok_requires_rust_rcon_when_group_message_enabled() -> None:
    from shared.config.types import AppConfigSnapshot

    probe = _load_probe_module()
    snap = AppConfigSnapshot(
        message_group_restrict=True,
        message_enabled_group_ids=["123"],
    )
    assert not probe._policy_ok(snap, group_id="123", user_id="1", private=False)


def test_policy_ok_allows_group_when_both_policies_enabled() -> None:
    from shared.config.rust_rcon_policy import RustRconGroupPolicyRecord
    from shared.config.types import AppConfigSnapshot

    probe = _load_probe_module()
    snap = AppConfigSnapshot(
        message_group_restrict=True,
        message_enabled_group_ids=["123"],
        rust_rcon_group_policies={
            "123": RustRconGroupPolicyRecord(group_id="123", enabled=True),
        },
    )
    assert probe._policy_ok(snap, group_id="123", user_id="1", private=False)


def test_policy_ok_blocks_disabled_private_message() -> None:
    from shared.config.rust_rcon_policy import RustRconUserPolicyRecord
    from shared.config.types import AppConfigSnapshot

    probe = _load_probe_module()
    snap = AppConfigSnapshot(
        message_private_restrict=True,
        message_enabled_user_ids=["999"],
        rust_rcon_user_policies={
            "456": RustRconUserPolicyRecord(user_id="456", enabled=True),
        },
    )
    assert not probe._policy_ok(snap, group_id=None, user_id="456", private=True)


def test_orm_lifespan_startup_shutdown(monkeypatch) -> None:
    probe = _load_probe_module()
    probe._ORM_SYNC_INITIALIZED = True

    calls = {"startup": 0, "shutdown": 0}

    class _FakeLifespan:
        async def startup(self) -> None:
            calls["startup"] += 1

        async def shutdown(self, **_kwargs) -> None:
            calls["shutdown"] += 1

    import nonebot

    monkeypatch.setattr(
        nonebot,
        "get_driver",
        lambda: SimpleNamespace(_lifespan=_FakeLifespan()),
    )

    async def _run() -> None:
        await probe._start_orm_lifespan()
        assert calls["startup"] == 1
        assert probe._ORM_LIFESPAN_ACTIVE
        await probe._stop_orm_lifespan()
        assert calls["shutdown"] == 1
        assert not probe._ORM_LIFESPAN_ACTIVE

    asyncio.run(_run())
