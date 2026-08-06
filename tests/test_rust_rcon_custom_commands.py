"""Tests for Rust RCON custom command matching and templates."""

from __future__ import annotations

import pytest

from shared.config.command_aliases import CommandAliasEntry
from shared.config.rust_rcon import RustRconBindingRecord
from shared.config.rust_rcon_custom import (
    RustRconCustomCommandRecord,
    alias_custom_command_conflict,
    command_aliases_custom_command_conflict,
    custom_command_name_conflict,
    is_qq_allowed_for_custom_command,
    match_rust_rcon_custom_command,
    normalize_custom_command_name,
    normalize_custom_command_template,
    render_custom_command_template,
    resolve_steamid_target,
    template_needs_steamid,
)
from shared.config.types import AppConfigSnapshot

_VALID_STEAM = "76561198000000000"


def _cmd(
    *,
    id: int = 1,
    name: str = "功能10",
    template: str = "giveto {steamid} wood 1",
    binding_id: int = 1,
    enabled: bool = True,
    allowed_qq_ids: tuple[str, ...] = ("10001",),
) -> RustRconCustomCommandRecord:
    return RustRconCustomCommandRecord(
        id=id,
        name=name,
        template=template,
        binding_id=binding_id,
        enabled=enabled,
        allowed_qq_ids=allowed_qq_ids,
    )


def test_normalize_custom_command_name() -> None:
    assert normalize_custom_command_name(" 功能10 ") == "功能10"
    with pytest.raises(ValueError):
        normalize_custom_command_name("功能 10")
    with pytest.raises(ValueError):
        normalize_custom_command_name("")


def test_normalize_and_render_template() -> None:
    template = normalize_custom_command_template(" giveto {steamid} wood 1 ")
    assert template_needs_steamid(template)
    assert (
        render_custom_command_template(template, _VALID_STEAM)
        == f"giveto {_VALID_STEAM} wood 1"
    )
    assert render_custom_command_template("status", None) == "status"
    with pytest.raises(ValueError):
        render_custom_command_template("giveto {steamid} wood 1", None)


def test_match_custom_command_longest_name() -> None:
    commands = [
        _cmd(id=1, name="功能", template="say a"),
        _cmd(id=2, name="功能10", template="say b"),
    ]
    matched = match_rust_rcon_custom_command("功能10 76561198000000000", commands)
    assert matched is not None
    command, remainder = matched
    assert command.id == 2
    assert remainder == "76561198000000000"


def test_match_custom_command_respects_enabled_binding() -> None:
    commands = [_cmd(binding_id=2)]
    assert (
        match_rust_rcon_custom_command(
            "功能10",
            commands,
            enabled_binding_ids={1},
        )
        is None
    )
    matched = match_rust_rcon_custom_command(
        "功能10",
        commands,
        enabled_binding_ids={2},
    )
    assert matched is not None


def test_resolve_steamid_target_prefers_mention() -> None:
    kind, value = resolve_steamid_target(_VALID_STEAM, ["10001"])
    assert kind == "qq"
    assert value == "10001"

    kind, value = resolve_steamid_target(_VALID_STEAM, [])
    assert kind == "steamid"
    assert value == _VALID_STEAM

    kind, value = resolve_steamid_target("12345", [])
    assert kind == "invalid_steamid"

    kind, value = resolve_steamid_target("", [])
    assert kind is None


def test_custom_command_name_conflict() -> None:
    snap = AppConfigSnapshot(
        command_aliases={
            "rust_player_checkin": CommandAliasEntry(enabled=True, triggers=["签到"]),
        },
        rust_rcon_bindings=[
            RustRconBindingRecord(
                id=1,
                alias="rcon1",
                host="127.0.0.1",
                port=28016,
                password="x",
                enabled=True,
            )
        ],
        rust_rcon_custom_commands=[_cmd(id=9, name="功能10")],
    )
    assert custom_command_name_conflict("签到", snap) is not None
    assert custom_command_name_conflict("签到奖励", snap) is not None
    assert custom_command_name_conflict("奖励签到", snap) is not None
    assert custom_command_name_conflict("rcon1", snap) is not None
    assert custom_command_name_conflict("功能10", snap) is not None
    assert custom_command_name_conflict("功能10", snap, exclude_id=9) is None
    assert custom_command_name_conflict("功能11", snap) is None
    assert alias_custom_command_conflict("功能10", snap.rust_rcon_custom_commands)


def test_custom_command_name_conflict_strips_command_prefix() -> None:
    snap = AppConfigSnapshot(
        rust_rcon_bindings=[
            RustRconBindingRecord(
                id=1,
                alias="/kill",
                host="127.0.0.1",
                port=28016,
                password="x",
                enabled=True,
            )
        ],
        rust_rcon_custom_commands=[_cmd(id=2, name="/heal")],
    )
    assert custom_command_name_conflict("kill", snap) is not None
    assert custom_command_name_conflict("/kill", snap) is not None
    assert custom_command_name_conflict("heal", snap) is not None
    assert custom_command_name_conflict("xyz", snap) is None
    assert alias_custom_command_conflict("/heal", [_cmd(id=3, name="heal")])
    assert alias_custom_command_conflict("heal", [_cmd(id=3, name="/heal")])
    assert alias_custom_command_conflict("/xyz", [_cmd(id=3, name="heal")]) is None


def test_command_aliases_custom_command_fuzzy_conflict() -> None:
    commands = [_cmd(id=1, name="签到奖励", enabled=True)]
    config = {
        "rust_player_checkin": CommandAliasEntry(enabled=True, triggers=["签到"]),
    }
    assert command_aliases_custom_command_conflict(config, commands) is not None
    assert (
        command_aliases_custom_command_conflict(
            config, [_cmd(id=1, name="签到奖励", enabled=False)]
        )
        is None
    )
    assert (
        command_aliases_custom_command_conflict(
            {
                "rust_player_checkin": CommandAliasEntry(
                    enabled=True, triggers=["积分"]
                ),
            },
            commands,
        )
        is None
    )


def test_is_qq_allowed_for_custom_command() -> None:
    command = _cmd(allowed_qq_ids=("10001", "10002"))
    assert is_qq_allowed_for_custom_command(command, "10001")
    assert not is_qq_allowed_for_custom_command(command, "99999")
    assert not is_qq_allowed_for_custom_command(_cmd(allowed_qq_ids=()), "10001")
