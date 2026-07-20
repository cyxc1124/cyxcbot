"""Tests for shared/config/command_aliases.py: parsing, defaults, matching."""

from __future__ import annotations

import re

import shared.config.command_aliases as command_aliases_module
from shared.config.command_aliases import (
    COMMAND_DEFAULTS,
    DEFAULT_EXTRA_PREFIXES,
    CommandAliasEntry,
    command_prefixes,
    default_config,
    find_trigger_conflicts,
    match_command_arg,
    match_plain,
    merge_partial_command_aliases,
    normalize_command_aliases,
    normalize_extra_prefixes,
    prefix_alternation,
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


def test_partial_update_merge_pattern_preserves_untouched_commands() -> None:
    """回归测试：PATCH /settings 只传部分命令时，未提及的命令应保留原有配置，
    而不是被 normalize_command_aliases 的缺省填充逻辑重置为出厂默认
    （见 admin/api/v1/settings.py::update_settings 的合并写法）。"""
    current = normalize_command_aliases(
        {
            "status": {"enabled": False, "triggers": ["status"]},
            "live_monitor_list": {"enabled": True, "triggers": ["自定义列表"]},
        }
    )
    current_serialized = serialize_command_aliases(current)

    # 只想改 live_status 一条（模拟客户端已带上完整字段的场景）
    patch = {"live_status": {"enabled": True, "triggers": ["直播", "查播"]}}
    merged = normalize_command_aliases(
        merge_partial_command_aliases(current_serialized, patch)
    )

    assert merged["live_status"].triggers == ["直播", "查播"]
    # 未提及的命令保留原值，而非被重置为出厂默认
    assert merged["status"].enabled is False
    assert merged["status"].triggers == ["status"]
    assert merged["live_monitor_list"].triggers == ["自定义列表"]


def test_merge_partial_command_aliases_keeps_untouched_fields_within_a_command() -> (
    None
):
    """回归测试：同一条命令内只传 enabled（或只传 triggers）时，另一个字段
    应保留原值，而不是被 Pydantic 为未传字段填的默认值
    （enabled=True/triggers=[]）整条覆盖——这要求调用方先用
    ``model_dump(exclude_unset=True)`` 筛出真正传入的字段，本函数只负责合并
    （见 admin/api/v1/settings.py::update_settings 及 issue：只关开关会清空触发
    词、只改触发词会误重启用）。"""
    current = serialize_command_aliases(
        normalize_command_aliases(
            {"status": {"enabled": True, "triggers": ["status", "状态"]}}
        )
    )

    # 只传 enabled=False（模拟 exclude_unset 后的结果，不含 triggers）
    merged = normalize_command_aliases(
        merge_partial_command_aliases(current, {"status": {"enabled": False}})
    )
    assert merged["status"].enabled is False
    assert merged["status"].triggers == ["status", "状态"]

    # 只传 triggers（模拟 exclude_unset 后的结果，不含 enabled），仍应保持禁用
    current2 = serialize_command_aliases(merged)
    merged2 = normalize_command_aliases(
        merge_partial_command_aliases(current2, {"status": {"triggers": ["新触发词"]}})
    )
    assert merged2["status"].enabled is False
    assert merged2["status"].triggers == ["新触发词"]


def test_command_alias_entry_model_dump_exclude_unset_matches_endpoint_usage() -> None:
    """确认 admin 端点实际依赖的 Pydantic 行为：嵌套在 SettingsUpdateRequest 里的
    CommandAliasEntryModel，未在请求体中出现的字段不会被 exclude_unset 带出
    （即使该字段有默认值），这是 merge_partial_command_aliases 能生效的前提。"""
    from admin.schemas.settings import SettingsUpdateRequest

    body = SettingsUpdateRequest.model_validate(
        {"command_aliases": {"status": {"enabled": False}}}
    )
    assert body.command_aliases is not None
    dumped = body.command_aliases["status"].model_dump(exclude_unset=True)
    assert dumped == {"enabled": False}

    body2 = SettingsUpdateRequest.model_validate(
        {"command_aliases": {"status": {"triggers": ["新触发词"]}}}
    )
    assert body2.command_aliases is not None
    dumped2 = body2.command_aliases["status"].model_dump(exclude_unset=True)
    assert dumped2 == {"triggers": ["新触发词"]}


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


def test_find_trigger_conflicts_ignores_disabled_commands() -> None:
    """回归测试：已禁用命令保留的触发词不参与冲突判定，否则关闭后触发词会保留
    这一设计就无法用来腾出触发词给别的命令复用（见 issue：禁用"群头衔设置"后仍
    无法把"头衔"配给别的启用命令）。"""
    config = normalize_command_aliases(
        {
            "group_special_title": {"enabled": False, "triggers": ["头衔"]},
            "live_monitor_list": {"enabled": True, "triggers": ["头衔"]},
        }
    )
    assert find_trigger_conflicts(config) == {}
    assert validation_error(config) is None

    # 两条都启用时仍应判定为冲突
    both_enabled = normalize_command_aliases(
        {
            "group_special_title": {"enabled": True, "triggers": ["头衔"]},
            "live_monitor_list": {"enabled": True, "triggers": ["头衔"]},
        }
    )
    assert "头衔" in find_trigger_conflicts(both_enabled)


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


def test_match_plain_bare_and_prefixed_text(monkeypatch) -> None:
    # 显式固定前缀集合，不依赖进程内是否已有其它测试初始化过 NoneBot driver /
    # 修改过 ConfigService 单例里的 command_extra_prefixes
    monkeypatch.setattr(
        command_aliases_module, "_configured_command_starts", lambda: frozenset({"/"})
    )
    monkeypatch.setattr(
        command_aliases_module, "_extra_prefixes", lambda: frozenset({"!"})
    )
    config = default_config()
    assert match_plain("最新动态", "dynamic_query_latest", config)
    assert match_plain("/最新动态", "dynamic_query_latest", config)
    assert match_plain("!最新动态", "dynamic_query_latest", config)
    assert not match_plain("随便说点什么", "dynamic_query_latest", config)


def test_match_plain_bare_trigger_still_matches_when_prefix_overlaps_it(
    monkeypatch,
) -> None:
    """回归测试：自定义前缀恰好是触发词的开头时（如前缀 "s" 与触发词
    "status"），裸触发词会先被 _strip_command_prefix 剥掉一段变成 "tatus"
    再判定不匹配，导致裸触发词失效——即使 UI 承诺裸触发词始终可用（见 issue：
    Preserve bare trigger matching when a prefix overlaps it）。"""
    monkeypatch.setattr(
        command_aliases_module, "_configured_command_starts", lambda: frozenset({"/"})
    )
    monkeypatch.setattr(
        command_aliases_module, "_extra_prefixes", lambda: frozenset({"s"})
    )
    config = normalize_command_aliases(
        {"status": {"enabled": True, "triggers": ["status"]}}
    )
    assert match_plain("status", "status", config)
    assert match_plain("/status", "status", config)
    # "s" + "status" 恰好也是合法的前缀+触发词组合，应继续匹配
    assert match_plain("sstatus", "status", config)


def test_match_plain_at_bot_fuzzy_prefix_suffix() -> None:
    config = default_config()
    assert match_plain("最新动态呀", "dynamic_query_latest", config, is_tome=True)
    assert match_plain("麻烦看下最新动态", "dynamic_query_latest", config, is_tome=True)
    # 非 @机器人 场景下不做模糊匹配
    assert not match_plain("最新动态呀", "dynamic_query_latest", config, is_tome=False)


def test_match_plain_exact_match_elsewhere_suppresses_fuzzy_match() -> None:
    """回归测试：最新动态用"动态"、置顶动态用"最新动态"时，@机器人 精确命中
    "最新动态" 不应被"最新动态查询"的模糊后缀匹配("动态"是"最新动态"的后缀)
    抢占分派（见 issue：@bot 最新动态 被误判为查最新动态而非置顶动态）。"""
    config = normalize_command_aliases(
        {
            "dynamic_query_latest": {"enabled": True, "triggers": ["动态"]},
            "dynamic_query_pinned": {"enabled": True, "triggers": ["最新动态"]},
        }
    )
    assert not match_plain("最新动态", "dynamic_query_latest", config, is_tome=True)
    assert match_plain("最新动态", "dynamic_query_pinned", config, is_tome=True)

    # 精确命中的命令若被禁用，则不应再抑制其他命令的模糊匹配
    disabled_pinned = normalize_command_aliases(
        {
            "dynamic_query_latest": {"enabled": True, "triggers": ["动态"]},
            "dynamic_query_pinned": {"enabled": False, "triggers": ["最新动态"]},
        }
    )
    assert match_plain(
        "最新动态", "dynamic_query_latest", disabled_pinned, is_tome=True
    )


def test_match_plain_prefers_longer_fuzzy_match_embedded_in_sentence() -> None:
    """回归测试：即使整条消息不逐字等于任何触发词，句子里嵌了重叠触发词时
    （"请看最新动态" 同时以 "动态"/"最新动态" 结尾），也应让更长、更具体的
    触发词优先命中，而不仅是消息恰好等于触发词的极限情形（见 issue：@bot 请看
    最新动态 仍被误判为查最新动态而非置顶动态）。"""
    config = normalize_command_aliases(
        {
            "dynamic_query_latest": {"enabled": True, "triggers": ["动态"]},
            "dynamic_query_pinned": {"enabled": True, "triggers": ["最新动态"]},
        }
    )
    assert not match_plain("请看最新动态", "dynamic_query_latest", config, is_tome=True)
    assert match_plain("请看最新动态", "dynamic_query_pinned", config, is_tome=True)


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


def test_match_command_arg_extracts_trailing_argument(monkeypatch) -> None:
    monkeypatch.setattr(
        command_aliases_module, "_configured_command_starts", lambda: frozenset({"/"})
    )
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


def test_command_prefixes_falls_back_to_slash_without_nonebot_start(
    monkeypatch,
) -> None:
    # 未拿到有效 COMMAND_START（如未初始化 NoneBot）时，回退为默认的 "/"。
    # 显式让 get_driver() 报错，不依赖进程内是否已有其它测试真正初始化过 driver。
    def _raise() -> None:
        raise RuntimeError("driver not initialized")

    monkeypatch.setattr("nonebot.get_driver", _raise)
    assert "/" in command_prefixes()


def test_prefix_matching_follows_configured_command_start(monkeypatch) -> None:
    """回归测试：迁移自 on_command 的命令必须跟随部署方配置的 COMMAND_START，
    而不是硬编码 "/"（见 issue：#status 不匹配、/status 仍误匹配）。"""
    monkeypatch.setattr(
        command_aliases_module, "_configured_command_starts", lambda: frozenset({"#"})
    )
    monkeypatch.setattr(
        command_aliases_module, "_extra_prefixes", lambda: frozenset({"!"})
    )
    config = default_config()

    assert match_plain("#status", "status", config)
    assert not match_plain("/status", "status", config)
    assert match_command_arg("#直播状态 12345", "live_status", config) == "12345"
    assert match_command_arg("/直播状态 12345", "live_status", config) is None

    # 习惯性前缀与 COMMAND_START 无关，始终生效
    assert match_plain("!status", "status", config)


def test_prefix_alternation_covers_configured_and_extra_prefixes(monkeypatch) -> None:
    monkeypatch.setattr(
        command_aliases_module, "_configured_command_starts", lambda: frozenset({"/"})
    )
    monkeypatch.setattr(
        command_aliases_module,
        "_extra_prefixes",
        lambda: frozenset({"!", "。", ".", "#"}),
    )
    parts = set(prefix_alternation().split("|"))
    assert parts == {re.escape(p) for p in ("/", "!", "。", ".", "#")}


def test_extra_prefixes_include_hash_for_extract_and_title_style_commands() -> None:
    # #提取/#头衔 等命令历史上固定使用 "#"，现改为跟随统一的前缀集合，
    # 因此出厂默认值需保留 "#"，避免默认部署下语义变化。
    assert "#" in DEFAULT_EXTRA_PREFIXES


def test_normalize_extra_prefixes_cleans_dedups_and_caps() -> None:
    cleaned = normalize_extra_prefixes(["  ! ", "!", "", "。", "a" * 10])
    # 去空白、去重、丢弃超长前缀
    assert cleaned == ["!", "。"]


def test_normalize_extra_prefixes_malformed_input_returns_empty() -> None:
    assert normalize_extra_prefixes("not-a-list") == []
    assert normalize_extra_prefixes(None) == []


def test_normalize_extra_prefixes_preserves_explicit_empty_choice() -> None:
    # 显式保存空列表代表“不启用任何习惯性前缀”，不应被强制回退为出厂默认值
    assert normalize_extra_prefixes([]) == []


def test_command_prefixes_respects_configured_extra_prefixes(monkeypatch) -> None:
    monkeypatch.setattr(
        command_aliases_module, "_configured_command_starts", lambda: frozenset({"/"})
    )
    monkeypatch.setattr(
        command_aliases_module, "_extra_prefixes", lambda: frozenset({"~"})
    )
    assert command_prefixes() == frozenset({"/", "~"})
