"""Tests for Rust RCON binding message matching."""

from __future__ import annotations

from shared.config.rust_rcon import RustRconBindingRecord, match_rust_rcon_binding


def _binding(alias: str) -> RustRconBindingRecord:
    return RustRconBindingRecord(
        id=1,
        alias=alias,
        host="127.0.0.1",
        port=28016,
        password="secret",
        enabled=True,
        allowed_qq_ids=("123",),
    )


def test_match_rust_rcon_binding_command() -> None:
    bindings = [_binding("rcon1")]
    matched = match_rust_rcon_binding("rcon1 status", bindings)
    assert matched is not None
    binding, command = matched
    assert binding.alias == "rcon1"
    assert command == "status"


def test_match_rust_rcon_binding_longest_alias_wins() -> None:
    bindings = [_binding("rcon"), _binding("rcon1")]
    matched = match_rust_rcon_binding("rcon1 say hi", bindings)
    assert matched is not None
    binding, command = matched
    assert binding.alias == "rcon1"
    assert command == "say hi"


def test_match_rust_rcon_binding_ignores_disabled() -> None:
    disabled = RustRconBindingRecord(
        id=2,
        alias="rcon1",
        host="127.0.0.1",
        port=28016,
        password="secret",
        enabled=False,
    )
    assert match_rust_rcon_binding("rcon1 status", [disabled]) is None


def test_match_rust_rcon_binding_exact_alias_empty_command() -> None:
    matched = match_rust_rcon_binding("rcon1", [_binding("rcon1")])
    assert matched == (_binding("rcon1"), "")
