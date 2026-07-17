"""Tests for shared/config/command_aliases.py: parsing, defaults, matching."""

from __future__ import annotations

from shared.config.command_aliases import (
    COMMAND_DEFAULTS,
    CommandAliasEntry,
    default_config,
    find_trigger_conflicts,
    match_command_arg,
    match_plain,
    normalize_command_aliases,
    resolve_entry,
    serialize_command_aliases,
    trigger_alternation,
    validation_error,
)


def test_normalize_fills_missing_ids_with_defaults() -> None:
    config = normalize_command_aliases({})
    assert set(config) == set(COMMAND_DEFAULTS)
    for command_id, defaults in COMMAND_DEFAULTS.items():
        assert config[command_id] == CommandAliasEntry(
            enabled=True, triggers=list(defaults)
        )


def test_normalize_overrides_default_triggers() -> None:
    config = normalize_command_aliases(
        {"status": {"enabled": True, "triggers": ["机器状态"]}}
    )
    assert config["status"].triggers == ["机器状态"]
    # 未提及的命令仍回退默认
    assert config["live_status"].triggers == COMMAND_DEFAULTS["live_status"]


def test_normalize_respects_disabled_flag_and_keeps_triggers() -> None:
    config = normalize_command_aliases(
        {"status": {"enabled": False, "triggers": ["status", "状态"]}}
    )
    assert config["status"].enabled is False
    assert config["status"].triggers == ["status", "状态"]


def test_normalize_cleans_triggers() -> None:
    config = normalize_command_aliases(
        {
            "status": {
                "enabled": True,
                "triggers": ["  status ", "", "status", "a" * 40],
            }
        }
    )
    # 去空白、去重、丢弃超长词
    assert config["status"].triggers == ["status"]


def test_normalize_drops_unknown_ids() -> None:
    config = normalize_command_aliases(
        {"not_a_real_command": {"enabled": True, "triggers": ["x"]}}
    )
    assert "not_a_real_command" not in config


def test_normalize_ignores_malformed_entry() -> None:
    config = normalize_command_aliases({"status": "not-a-dict"})
    assert config["status"].triggers == COMMAND_DEFAULTS["status"]


def test_serialize_round_trips_through_normalize() -> None:
    config = default_config()
    config["status"] = CommandAliasEntry(enabled=False, triggers=["机器状态"])
    payload = serialize_command_aliases(config)
    restored = normalize_command_aliases(payload)
    assert restored["status"] == config["status"]


def test_resolve_entry_falls_back_to_default_for_missing_id() -> None:
    entry = resolve_entry("status", {})
    assert entry.enabled is True
    assert entry.triggers == COMMAND_DEFAULTS["status"]


def test_validation_error_flags_enabled_with_empty_triggers() -> None:
    config = normalize_command_aliases({"status": {"enabled": True, "triggers": []}})
    error = validation_error(config)
    assert error is not None
    assert "运行状态查询" in error


def test_validation_error_flags_cross_command_conflicts() -> None:
    config = normalize_command_aliases(
        {"live_monitor_list": {"enabled": True, "triggers": ["头衔"]}}
    )
    conflicts = find_trigger_conflicts(config)
    assert conflicts.get("头衔") == ["live_monitor_list", "group_special_title"]
    assert validation_error(config) is not None


def test_validation_error_none_for_default_config() -> None:
    assert validation_error(default_config()) is None


def test_trigger_alternation_none_when_disabled_or_empty() -> None:
    disabled = normalize_command_aliases(
        {"status": {"enabled": False, "triggers": ["status"]}}
    )
    assert trigger_alternation("status", disabled) is None


def test_trigger_alternation_escapes_and_orders_by_length() -> None:
    config = normalize_command_aliases(
        {"dynamic_extract": {"enabled": True, "triggers": ["a", "abc"]}}
    )
    assert trigger_alternation("dynamic_extract", config) == "abc|a"


def test_match_plain_bare_and_prefixed_text() -> None:
    config = default_config()
    assert match_plain("最新动态", "dynamic_query_latest", config)
    assert match_plain("/最新动态", "dynamic_query_latest", config)
    assert match_plain("!最新动态", "dynamic_query_latest", config)
    assert not match_plain("随便说点什么", "dynamic_query_latest", config)


def test_match_plain_at_bot_fuzzy_prefix_suffix() -> None:
    config = default_config()
    assert match_plain("最新动态呀", "dynamic_query_latest", config, is_tome=True)
    assert match_plain("麻烦看下最新动态", "dynamic_query_latest", config, is_tome=True)
    # 非 @机器人 场景下不做模糊匹配
    assert not match_plain("最新动态呀", "dynamic_query_latest", config, is_tome=False)


def test_match_plain_respects_custom_triggers_and_disabled() -> None:
    config = normalize_command_aliases(
        {"status": {"enabled": True, "triggers": ["查状态"]}}
    )
    assert match_plain("查状态", "status", config)
    assert not match_plain("status", "status", config)

    disabled = normalize_command_aliases(
        {"status": {"enabled": False, "triggers": ["status"]}}
    )
    assert not match_plain("status", "status", disabled)


def test_match_command_arg_extracts_trailing_argument() -> None:
    config = default_config()
    assert match_command_arg("/直播状态 12345", "live_status", config) == "12345"
    assert match_command_arg("直播状态 12345", "live_status", config) == "12345"
    assert match_command_arg("直播状态", "live_status", config) == ""
    assert match_command_arg("直播状态abc", "live_status", config) is None
    assert match_command_arg("随便说点什么", "live_status", config) is None


def test_match_command_arg_none_when_disabled() -> None:
    disabled = normalize_command_aliases(
        {"live_status": {"enabled": False, "triggers": ["直播状态"]}}
    )
    assert match_command_arg("直播状态 12345", "live_status", disabled) is None
