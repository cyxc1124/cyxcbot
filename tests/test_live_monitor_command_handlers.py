"""plugins/live_monitor/__init__.py 命令处理器测试（issue #150）。

覆盖点：`直播状态`/`监控列表` 必须读取模块级最新的 live_monitor_instance
（而非导入时绑定的 stale 引用），且实例未启动时的临时查询不得关闭
共享的全局 api_manager。
"""

from __future__ import annotations

import os
import sys
from unittest.mock import DEFAULT, AsyncMock, MagicMock, patch

import nonebot
import pytest


def _ensure_nonebot() -> None:
    os.environ.setdefault("SQLALCHEMY_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(
            sqlalchemy_database_url=os.environ["SQLALCHEMY_DATABASE_URL"],
            alembic_startup_check=False,
        )
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")
    if "nonebot_plugin_apscheduler" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_apscheduler")


_ensure_nonebot()

import plugins.live_monitor as live_monitor_plugin  # noqa: E402
from plugins.live_monitor import live_monitor as live_monitor_mod  # noqa: E402
from plugins.live_monitor.config import Config  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_live_monitor_instance():
    live_monitor_mod.live_monitor_instance = None
    yield
    live_monitor_mod.live_monitor_instance = None


def _make_event(
    group_id: int = 123, text: str = "", is_tome: bool = False
) -> MagicMock:
    event = MagicMock()
    event.group_id = group_id
    event.get_plaintext.return_value = text
    event.is_tome.return_value = is_tome
    return event


def _command_snapshot(aliases):
    from shared.config.rust_rcon_policy import RustRconGroupPolicyRecord
    from shared.config.types import AppConfigSnapshot

    return AppConfigSnapshot(
        command_aliases=aliases,
        status_check_group_restrict=False,
        status_check_private_restrict=False,
        rust_rcon_group_policies={
            "456": RustRconGroupPolicyRecord(group_id="456", enabled=True)
        },
        dynamic_monitor_mapping={"42": ["123", "456", "test-group"]},
    )


def _patch_matcher(matcher):
    return patch.multiple(matcher, send=DEFAULT, finish=DEFAULT)


@pytest.mark.asyncio
async def test_live_status_uses_instance_set_after_module_import() -> None:
    """启动后才赋值的 live_monitor_instance 必须被 直播状态 命令读取到，而非 import 时的 stale None。"""
    fake_instance = MagicMock()
    fake_instance.check_room_now = AsyncMock(
        return_value={
            "room_id": 12345,
            "streamer_name": "测试主播",
            "title": "测试标题",
            "is_living": True,
            "live_status": "LIVE",
            "area": "分区A - 分区B",
            "online": 100,
        }
    )
    # 模拟 start_live_monitor() 在运行期赋值模块属性（而不是通过 __init__.py 里绑定的旧引用）
    live_monitor_mod.live_monitor_instance = fake_instance

    event = _make_event(text="直播状态 12345")

    with _patch_matcher(live_monitor_plugin.live_status_cmd) as mocks:
        await live_monitor_plugin.handle_live_status(MagicMock(), event)

    fake_instance.check_room_now.assert_awaited_once_with("12345")
    mocks["finish"].assert_awaited_once()
    assert "测试主播" in str(mocks["finish"].await_args.args[0])


@pytest.mark.asyncio
async def test_live_status_without_instance_does_not_close_shared_api_manager() -> None:
    """实例未启动时的临时查询必须使用独立 session，不能调用共享 api_manager.close()。"""
    live_monitor_mod.live_monitor_instance = None

    fake_room_info = MagicMock()
    fake_room_info.room_id = 12345
    fake_room_info.title = "测试标题"
    fake_room_info.is_living.return_value = False
    fake_room_info.live_status.name = "PREPARING"
    fake_room_info.parent_area_name = "分区A"
    fake_room_info.area_name = "分区B"
    fake_room_info.online = 0

    event = _make_event(text="直播状态 12345")

    with (
        patch(
            "plugins.live_monitor.Config.from_service",
            return_value=Config(bilibili_cookie=None),
        ),
        patch(
            "utils.bilibili_api.live_api.LiveApi.get_room_and_user_info",
            new=AsyncMock(return_value=(fake_room_info, None)),
        ),
        patch(
            "utils.bilibili_api.api_manager.init", new_callable=AsyncMock
        ) as shared_init,
        patch(
            "utils.bilibili_api.api_manager.close", new_callable=AsyncMock
        ) as shared_close,
        _patch_matcher(live_monitor_plugin.live_status_cmd) as mocks,
    ):
        await live_monitor_plugin.handle_live_status(MagicMock(), event)

    shared_init.assert_not_awaited()
    shared_close.assert_not_awaited()
    mocks["finish"].assert_awaited_once()
    assert "房间12345" in str(mocks["finish"].await_args.args[0])


@pytest.mark.asyncio
async def test_list_monitor_uses_instance_set_after_module_import() -> None:
    """`监控列表` 命令必须能读取到运行中实例的最新 room_states。"""
    fake_state = MagicMock()
    fake_state.user_info.name = "测试主播"
    fake_state.room_info.is_living.return_value = True

    fake_instance = MagicMock()
    fake_instance.room_states = {"12345": fake_state}
    live_monitor_mod.live_monitor_instance = fake_instance

    fake_config = Config(live_monitor_mapping={"12345": ["123"]})

    with (
        patch("plugins.live_monitor.Config.from_service", return_value=fake_config),
        _patch_matcher(live_monitor_plugin.list_monitor_cmd) as mocks,
    ):
        await live_monitor_plugin.handle_list_monitor(
            MagicMock(), _make_event(text="监控列表")
        )

    mocks["finish"].assert_awaited_once()
    message = str(mocks["finish"].await_args.args[0])
    assert "测试主播" in message
    assert "🔴" in message


@pytest.mark.asyncio
async def test_list_monitor_without_instance_falls_back_to_offline() -> None:
    """无运行中实例时，监控列表应展示离线占位而不是报错。"""
    live_monitor_mod.live_monitor_instance = None
    fake_config = Config(live_monitor_mapping={"12345": ["123"]})

    with (
        patch("plugins.live_monitor.Config.from_service", return_value=fake_config),
        _patch_matcher(live_monitor_plugin.list_monitor_cmd) as mocks,
    ):
        await live_monitor_plugin.handle_list_monitor(
            MagicMock(), _make_event(text="监控列表")
        )

    message = str(mocks["finish"].await_args.args[0])
    assert "房间12345" in message
    assert "⚫" in message


@pytest.mark.asyncio
@pytest.mark.parametrize("text, expected", [("/status", "live"), ("status", "status")])
async def test_prefixed_alias_only_runs_one_real_command_handler(
    monkeypatch, text, expected
):
    from types import SimpleNamespace

    from nonebot.exception import FinishedException

    from plugins.status_check import status_checker
    from shared.config.command_aliases import normalize_command_aliases

    aliases = normalize_command_aliases({"live_status": {"triggers": ["/status"]}})
    service = SimpleNamespace(get_snapshot=lambda: _command_snapshot(aliases))
    monkeypatch.setattr(live_monitor_plugin, "get_config_service", lambda: service)
    monkeypatch.setattr(status_checker, "get_config_service", lambda: service)
    monkeypatch.setattr(
        status_checker, "check_status_permission", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        status_checker, "get_bot_status", AsyncMock(return_value="机器人状态")
    )
    monkeypatch.setattr(
        "shared.config.command_aliases.command_prefixes", lambda: frozenset({"/"})
    )
    replies = []

    def finish(label):
        async def record(message):
            replies.append(label)
            raise FinishedException

        return record

    monkeypatch.setattr(status_checker.status_cmd, "finish", finish("status"))
    monkeypatch.setattr(live_monitor_plugin.live_status_cmd, "finish", finish("live"))
    bot, event = MagicMock(), _make_event(text=text)
    for handler in (
        status_checker.handle_status_command,
        live_monitor_plugin.handle_live_status,
    ):
        try:
            await handler(bot, event)
        except FinishedException:
            pass
    assert replies == [expected]


@pytest.mark.asyncio
@pytest.mark.parametrize("command_id", ["dynamic_extract", "group_special_title"])
@pytest.mark.parametrize("mentioned", [False, True])
async def test_prefix_required_alias_preserves_real_status_reply(
    monkeypatch, command_id, mentioned
):
    from types import SimpleNamespace

    from nonebot.exception import FinishedException

    from plugins.dynamic_monitor.dynamic_extract import parse_extract_dynamic_id
    from plugins.status_check import status_checker
    from shared.config.command_aliases import normalize_command_aliases
    from shared.group_special_title import parse_title_command

    aliases = normalize_command_aliases({command_id: {"triggers": ["/status"]}})
    service = SimpleNamespace(get_snapshot=lambda: _command_snapshot(aliases))
    monkeypatch.setattr(status_checker, "get_config_service", lambda: service)
    monkeypatch.setattr(
        status_checker, "check_status_permission", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        status_checker, "get_bot_status", AsyncMock(return_value="机器人状态")
    )
    monkeypatch.setattr(
        "shared.config.command_aliases.command_prefixes", lambda: frozenset({"/"})
    )
    finish = AsyncMock(side_effect=FinishedException)
    monkeypatch.setattr(status_checker.status_cmd, "finish", finish)
    with pytest.raises(FinishedException):
        await status_checker.handle_status_command(
            MagicMock(), _make_event(text="/status", is_tome=mentioned)
        )
    finish.assert_awaited_once_with("机器人状态")
    assert parse_extract_dynamic_id("/status", aliases) is None
    assert parse_title_command("/status", aliases) is None
    if command_id == "dynamic_extract":
        assert parse_extract_dynamic_id("//status1234567890", aliases) == "1234567890"
    else:
        assert parse_title_command("//status 测试", aliases) == "测试"


@pytest.mark.parametrize(
    "argument_command", ["live_status", "rust_player_bind", "rust_player_shop_redeem"]
)
def test_reverse_prefixed_argument_alias_conflicts_with_real_title_parser(
    monkeypatch, argument_command
):
    from shared.config.command_aliases import (
        match_command_arg,
        normalize_command_aliases,
        validation_error,
    )
    from shared.group_special_title import parse_title_command

    aliases = normalize_command_aliases(
        {
            "status": {"enabled": False},
            argument_command: {"triggers": ["/status"]},
            "group_special_title": {"triggers": ["status"]},
        }
    )
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    monkeypatch.setattr(
        "shared.config.command_aliases._extra_prefixes", lambda: frozenset()
    )
    assert match_command_arg("/status hello", argument_command, aliases) == "hello"
    assert parse_title_command("/status hello", aliases) == "hello"
    assert validation_error(aliases) is not None


@pytest.mark.parametrize("shop_trigger", ["/status", "/STATUS"])
def test_reverse_prefixed_shop_alias_conflicts_with_real_extract_parser(
    monkeypatch, shop_trigger
):
    from plugins.dynamic_monitor.dynamic_extract import parse_extract_dynamic_id
    from shared.config.command_aliases import (
        normalize_command_aliases,
        validation_error,
    )
    from shared.config.rust_player import parse_shop_list_page

    aliases = normalize_command_aliases(
        {
            "status": {"enabled": False},
            "rust_player_shop_list": {"triggers": [shop_trigger]},
            "dynamic_extract": {"triggers": ["status"]},
        }
    )
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    monkeypatch.setattr(
        "shared.config.command_aliases._extra_prefixes", lambda: frozenset()
    )
    assert parse_shop_list_page(shop_trigger + "1234567890", aliases) == 1234567890
    assert (
        parse_extract_dynamic_id(shop_trigger + "1234567890", aliases) == "1234567890"
    )
    assert validation_error(aliases) is not None


def _scoped_event(scope, mentioned):
    from datetime import datetime, timezone

    from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
    from nonebot.adapters.qq.event import (
        C2CMessageCreateEvent,
        GroupAtMessageCreateEvent,
    )

    if scope.startswith("official"):
        cls = (
            GroupAtMessageCreateEvent
            if scope.endswith("group")
            else C2CMessageCreateEvent
        )
        return cls.model_validate(
            {
                "id": "scope-test",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "content": "/status",
                **(
                    {"group_id": "test-group", "group_openid": "test-group"}
                    if scope.endswith("group")
                    else {}
                ),
                "author": {
                    "id": "test-user",
                    "user_openid": "test-user",
                    "member_openid": "test-user",
                    "bot": False,
                    "member_role": "member",
                },
            }
        )
    cls = GroupMessageEvent if scope.endswith("group") else PrivateMessageEvent
    event = MagicMock(spec=cls)
    event.get_plaintext.return_value = "/status"
    event.is_tome.return_value = mentioned
    event.user_id = 123
    event.get_user_id.return_value = "123"
    event.get_type.return_value = "message"
    if scope.endswith("group"):
        event.group_id = 456
    return event


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "shadow_command",
    [
        "rust_player_checkin",
        "live_status",
        "dynamic_query_latest",
        "video_query_latest",
    ],
)
@pytest.mark.parametrize(
    "scope, mentioned",
    [
        ("official-c2c", True),
        ("official-group", True),
        ("onebot-private", True),
        ("onebot-group", True),
        ("onebot-group", False),
    ],
)
async def test_status_shadow_only_considers_commands_supported_in_event_scope(
    monkeypatch, shadow_command, scope, mentioned
):
    from types import SimpleNamespace

    from nonebot.exception import FinishedException

    from plugins.status_check import status_checker
    from shared.config.command_aliases import (
        command_aliases_for_event,
        match_plain,
        normalize_command_aliases,
    )

    aliases = normalize_command_aliases({shadow_command: {"triggers": ["/status"]}})
    service = SimpleNamespace(get_snapshot=lambda: _command_snapshot(aliases))
    monkeypatch.setattr(status_checker, "get_config_service", lambda: service)
    monkeypatch.setattr(
        status_checker, "check_status_permission", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        status_checker, "get_bot_status", AsyncMock(return_value="机器人状态")
    )
    monkeypatch.setattr(
        "shared.config.command_aliases.command_prefixes", lambda: frozenset({"/"})
    )
    finish = AsyncMock(side_effect=FinishedException)
    monkeypatch.setattr(status_checker.status_cmd, "finish", finish)
    event = _scoped_event(scope, mentioned)
    shadow_supported = scope.endswith("group") and (
        shadow_command != "rust_player_checkin"
        or (scope == "onebot-group" and mentioned)
    )
    if shadow_supported:
        await status_checker.handle_status_command(MagicMock(), event)
        finish.assert_not_awaited()
    else:
        with pytest.raises(FinishedException):
            await status_checker.handle_status_command(MagicMock(), event)
        finish.assert_awaited_once_with("机器人状态")

    scoped = await command_aliases_for_event(service.get_snapshot(), MagicMock(), event)
    assert scoped[shadow_command].enabled == shadow_supported
    assert aliases[shadow_command].triggers == ["/status"]
    if shadow_command == "rust_player_checkin":
        import plugins.rust_player as rust_player

        monkeypatch.setattr(rust_player, "get_config_service", lambda: service)
        monkeypatch.setattr(
            rust_player, "is_rust_rcon_enabled", lambda *args, **kwargs: True
        )
        consume = AsyncMock()
        monkeypatch.setattr(rust_player, "_handle_bind_or_checkin", consume)
        await rust_player.handle_rust_player(MagicMock(), event)
        assert consume.await_count == int(shadow_supported)
    elif shadow_command == "live_status":
        consume = AsyncMock(side_effect=FinishedException)
        monkeypatch.setattr(live_monitor_plugin, "get_config_service", lambda: service)
        monkeypatch.setattr(live_monitor_plugin.live_status_cmd, "finish", consume)
        if shadow_supported:
            with pytest.raises(FinishedException):
                await live_monitor_plugin.handle_live_status(MagicMock(), event)
            consume.assert_awaited_once()
        else:
            await live_monitor_plugin.handle_live_status(MagicMock(), event)
            consume.assert_not_awaited()
    elif shadow_supported:
        assert match_plain("/status", shadow_command, scoped, is_tome=mentioned)


@pytest.mark.parametrize(
    "required_command, required_trigger, text",
    [
        ("group_special_title", "status extra", "/status extra hello"),
        ("dynamic_extract", "status extra", "/status extra1234567890"),
    ],
)
def test_reverse_prefixed_argument_overlap_with_spaced_required_trigger(
    monkeypatch, required_command, required_trigger, text
):
    from plugins.dynamic_monitor.dynamic_extract import parse_extract_dynamic_id
    from shared.config.command_aliases import (
        match_command_arg,
        normalize_command_aliases,
        validation_error,
    )
    from shared.group_special_title import parse_title_command

    aliases = normalize_command_aliases(
        {
            "status": {"enabled": False},
            "live_status": {"triggers": ["/status"]},
            required_command: {"triggers": [required_trigger]},
        }
    )
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    monkeypatch.setattr(
        "shared.config.command_aliases._extra_prefixes", lambda: frozenset()
    )
    assert match_command_arg(text, "live_status", aliases) is not None
    if required_command == "dynamic_extract":
        assert parse_extract_dynamic_id(text, aliases) == "1234567890"
    else:
        assert parse_title_command(text, aliases) == "hello"
    assert validation_error(aliases) is not None


def test_reverse_title_and_shop_arguments_are_disjoint(monkeypatch):
    from shared.config.command_aliases import (
        normalize_command_aliases,
        validation_error,
    )
    from shared.config.rust_player import parse_shop_list_page
    from shared.group_special_title import parse_title_command

    aliases = normalize_command_aliases(
        {
            "status": {"enabled": False},
            "rust_player_shop_list": {"triggers": ["/status"]},
            "group_special_title": {"triggers": ["status"]},
        }
    )
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    monkeypatch.setattr(
        "shared.config.command_aliases._extra_prefixes", lambda: frozenset()
    )
    assert validation_error(aliases) is None
    assert parse_shop_list_page("/status1", aliases) == 1
    assert parse_title_command("/status1", aliases) is None
    assert parse_title_command("/status 1", aliases) == "1"
    assert parse_shop_list_page("/status 1", aliases) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "policy, group_id, rust_expected",
    [(None, 456, False), (False, 456, False), (True, 456, True), (True, 457, False)],
)
async def test_rust_group_policy_controls_real_alias_arbitration(
    monkeypatch, policy, group_id, rust_expected
):
    from types import SimpleNamespace

    from nonebot.exception import FinishedException

    import plugins.rust_player as rust_player
    from plugins.status_check import status_checker
    from shared.config.command_aliases import normalize_command_aliases
    from shared.config.rust_rcon_policy import RustRconGroupPolicyRecord
    from shared.config.types import AppConfigSnapshot

    snap = AppConfigSnapshot(
        command_aliases=normalize_command_aliases(
            {"rust_player_checkin": {"triggers": ["/status"]}}
        ),
        status_check_group_restrict=False,
    )
    if policy is not None:
        snap.rust_rcon_group_policies["456"] = RustRconGroupPolicyRecord(
            group_id="456", enabled=policy
        )
    service = SimpleNamespace(get_snapshot=lambda: snap)
    monkeypatch.setattr(status_checker, "get_config_service", lambda: service)
    monkeypatch.setattr(rust_player, "get_config_service", lambda: service)
    monkeypatch.setattr(
        status_checker, "get_bot_status", AsyncMock(return_value="机器人状态")
    )
    finish = AsyncMock(side_effect=FinishedException)
    consume = AsyncMock()
    monkeypatch.setattr(status_checker.status_cmd, "finish", finish)
    monkeypatch.setattr(rust_player, "_handle_bind_or_checkin", consume)
    event = _scoped_event("onebot-group", True)
    event.group_id = group_id
    event.get_user_id.return_value = "123"
    from nonebot.adapters.onebot.v11 import Bot

    bot = MagicMock(spec=Bot)
    bot.config.superusers = set()
    bot.adapter = MagicMock()
    bot.adapter.get_name.return_value = "OneBot V11"
    for handler in (
        status_checker.handle_status_command,
        rust_player.handle_rust_player,
    ):
        try:
            await handler(bot, event)
        except FinishedException:
            pass
    assert consume.await_count == int(rust_expected)
    assert finish.await_count == int(not rust_expected)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "allow_kind", ["deny", "group", "personal", "bare_superuser", "qualified_superuser"]
)
async def test_status_permission_controls_reverse_alias_arbitration(
    monkeypatch, allow_kind
):
    from types import SimpleNamespace

    from nonebot.exception import FinishedException

    from plugins.status_check import status_checker
    from shared.config.command_aliases import normalize_command_aliases
    from shared.config.types import AppConfigSnapshot

    snap = AppConfigSnapshot(
        command_aliases=normalize_command_aliases(
            {"status": {"triggers": ["/live"]}, "live_status": {"triggers": ["live"]}}
        )
    )
    if allow_kind == "group":
        snap.status_check_enabled_group_ids = ["456"]
    if allow_kind == "personal":
        snap.status_check_allowed_qq = ["123"]
    service = SimpleNamespace(get_snapshot=lambda: snap)
    monkeypatch.setattr(status_checker, "get_config_service", lambda: service)
    monkeypatch.setattr(live_monitor_plugin, "get_config_service", lambda: service)
    monkeypatch.setattr(
        status_checker, "get_bot_status", AsyncMock(return_value="机器人状态")
    )
    status_finish = AsyncMock(side_effect=FinishedException)
    live_finish = AsyncMock(side_effect=FinishedException)
    monkeypatch.setattr(status_checker.status_cmd, "finish", status_finish)
    monkeypatch.setattr(live_monitor_plugin.live_status_cmd, "finish", live_finish)
    event = _scoped_event("onebot-group", True)
    event.get_plaintext.return_value = "/live"
    event.get_user_id.return_value = "123"
    from nonebot.adapters.onebot.v11 import Bot

    bot = MagicMock(spec=Bot)
    bot.adapter = MagicMock()
    bot.adapter.get_name.return_value = "OneBot V11"
    bot.config.superusers = (
        {"123"}
        if allow_kind == "bare_superuser"
        else ({"onebot:123"} if allow_kind == "qualified_superuser" else set())
    )
    for handler in (
        status_checker.handle_status_command,
        live_monitor_plugin.handle_live_status,
    ):
        try:
            await handler(bot, event)
        except FinishedException:
            pass
    assert status_finish.await_count == int(allow_kind != "deny")
    assert live_finish.await_count == int(allow_kind == "deny")


@pytest.mark.parametrize(
    "user_id, group_id, private",
    [("", None, True), (" ", "456", False), ("123", "", False), ("123", " ", False)],
)
def test_status_snapshot_permission_requires_identity(user_id, group_id, private):
    from shared.config.types import AppConfigSnapshot
    from shared.status_check_policy import is_status_check_allowed_from_snapshot

    snap = AppConfigSnapshot(
        status_check_allowed_qq=["", " "],
        status_check_group_restrict=False,
        status_check_private_restrict=False,
    )
    assert not is_status_check_allowed_from_snapshot(
        user_id, snap, group_id=group_id, is_private=private
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query_command", ["dynamic_query_latest", "video_query_latest"]
)
@pytest.mark.parametrize("configured", [False, True])
async def test_query_group_mapping_controls_real_alias_arbitration(
    monkeypatch, query_command, configured
):
    from types import SimpleNamespace

    from nonebot.exception import FinishedException

    import plugins.dynamic_monitor as dynamic_plugin
    import plugins.video_monitor as video_plugin
    from plugins.dynamic_monitor import dynamic_monitor as dynamic_mod
    from plugins.status_check import status_checker
    from shared.config.command_aliases import normalize_command_aliases
    from utils.bilibili_api import video_api_manager

    snap = _command_snapshot(
        normalize_command_aliases({query_command: {"triggers": ["/status"]}})
    )
    snap.dynamic_monitor_mapping = {"42": ["456"]} if configured else {}
    service = SimpleNamespace(get_snapshot=lambda: snap)
    query_config = SimpleNamespace(
        get_uids_by_group_id=lambda gid: (
            ["42"] if gid in snap.dynamic_monitor_mapping.get("42", []) else []
        ),
        bilibili_cookie="",
    )
    for plugin in (status_checker, dynamic_plugin, video_plugin):
        monkeypatch.setattr(plugin, "get_config_service", lambda: service)
    monkeypatch.setattr(dynamic_plugin.Config, "from_service", lambda: query_config)
    monkeypatch.setattr(video_plugin, "get_cached_config", lambda: query_config)
    monkeypatch.setattr(
        dynamic_mod,
        "dynamic_monitor_instance",
        SimpleNamespace(
            is_running=True, get_latest_dynamic=AsyncMock(return_value="动态结果")
        ),
    )
    monkeypatch.setattr(video_api_manager, "init", AsyncMock())
    monkeypatch.setattr(
        video_api_manager, "get_user_videos", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        status_checker, "get_bot_status", AsyncMock(return_value="机器人状态")
    )
    finish = AsyncMock(side_effect=FinishedException)
    dynamic_send, video_send = AsyncMock(), AsyncMock()
    monkeypatch.setattr(status_checker.status_cmd, "finish", finish)
    monkeypatch.setattr(dynamic_plugin, "send_event_message", dynamic_send)
    monkeypatch.setattr(video_plugin, "send_event_text", video_send)
    event = _scoped_event("onebot-group", True)
    bot = MagicMock()
    for handler in (
        status_checker.handle_status_command,
        dynamic_plugin.handle_dynamic_commands
        if query_command.startswith("dynamic")
        else video_plugin.handle_video_commands,
    ):
        try:
            await handler(bot, event)
        except FinishedException:
            pass
    assert finish.await_count == int(not configured)
    assert (
        dynamic_send if query_command.startswith("dynamic") else video_send
    ).await_count == int(configured)


@pytest.mark.asyncio
@pytest.mark.parametrize("text, reply_count", [("/status", 1), ("普通聊天消息", 0)])
async def test_configured_dynamic_query_replies_when_service_unavailable(
    monkeypatch, text, reply_count
):
    from types import SimpleNamespace

    import plugins.dynamic_monitor as dynamic_plugin
    from plugins.dynamic_monitor import dynamic_monitor as dynamic_mod
    from shared.config.command_aliases import normalize_command_aliases

    snap = _command_snapshot(
        normalize_command_aliases({"dynamic_query_latest": {"triggers": ["/status"]}})
    )
    snap.dynamic_monitor_mapping = {"42": ["456"]}
    service = SimpleNamespace(get_snapshot=lambda: snap)
    query_config = SimpleNamespace(get_uids_by_group_id=lambda gid: ["42"])
    monkeypatch.setattr(dynamic_plugin, "get_config_service", lambda: service)
    monkeypatch.setattr(dynamic_plugin.Config, "from_service", lambda: query_config)
    monkeypatch.setattr(dynamic_mod, "dynamic_monitor_instance", None)
    send = AsyncMock()
    monkeypatch.setattr(dynamic_plugin, "send_event_text", send)
    event = _scoped_event("onebot-group", True)
    event.get_plaintext.return_value = text
    await dynamic_plugin.handle_dynamic_commands(MagicMock(), event)
    assert send.await_count == reply_count
    if reply_count:
        assert "服务暂不可用" in send.await_args.args[2]


@pytest.mark.asyncio
async def test_missing_group_identity_does_not_enable_group_routes():
    from shared.config.command_aliases import command_aliases_for_event, default_config

    snapshot = _command_snapshot(default_config())
    event = _scoped_event("onebot-group", True)
    event.group_id = " "
    scoped = await command_aliases_for_event(snapshot, MagicMock(), event)
    for command_id in (
        "status",
        "live_status",
        "live_monitor_list",
        "dynamic_query_latest",
        "video_query_latest",
        "rust_player_checkin",
    ):
        assert not scoped[command_id].enabled
