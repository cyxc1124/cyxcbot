"""Whole aliases own inputs; explicit argument grammar owns its free tail."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.exception import FinishedException
from test_live_monitor_command_handlers import _command_snapshot, _scoped_event

from shared.config.command_aliases import normalize_command_aliases, validation_error


def _actor():
    bot = MagicMock(spec=Bot)
    bot.config.superusers = set()
    bot.adapter = MagicMock()
    bot.adapter.get_name.return_value = "OneBot V11"
    return bot


def _event(message, scope="onebot-group"):
    event = _scoped_event(scope, True)
    event.message = Message(message)
    event.get_plaintext.return_value = event.message.extract_plain_text()
    return event


async def _run(handler, bot, event):
    try:
        await handler(bot, event)
    except FinishedException:
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("custom", [False, True], ids=["binding", "custom"])
@pytest.mark.parametrize(
    "name,text,old_prefixes,new_prefixes,old_rcon,new_rcon,edit_alias",
    [
        ("server", "$server status", [], ["$"], False, True, False),
        ("server", "server status", [], ["$"], True, True, False),
        ("!status", "!!status", [], ["!"], False, True, False),
        ("server", "$server status", ["$"], [], True, False, False),
        ("server", "!server status", ["!"], ["!"], True, True, True),
    ],
)
async def test_rcon_prefix_remainder_collisions_use_concrete_group_inputs(
    monkeypatch,
    custom,
    name,
    text,
    old_prefixes,
    new_prefixes,
    old_rcon,
    new_rcon,
    edit_alias,
):
    from nonebot.adapters.onebot.v11 import GroupMessageEvent

    import plugins.live_monitor as live_plugin
    import plugins.rust_rcon as rcon_plugin
    from plugins.status_check import status_checker
    from shared.config.command_aliases import COMMAND_DEFAULTS
    from shared.config.rust_rcon import RustRconBindingRecord
    from shared.config.rust_rcon_custom import RustRconCustomCommandRecord

    aliases = normalize_command_aliases(
        {
            cid: {"enabled": cid == "status", "triggers": ["status"]}
            for cid in COMMAND_DEFAULTS
        }
    )
    snap = _command_snapshot(aliases)
    snap.rust_rcon_bindings = [
        RustRconBindingRecord(
            id=1,
            alias="rcon1" if custom else name,
            host="localhost",
            port=28016,
            password="",
            allowed_qq_ids=("123",),
        )
    ]
    if custom:
        snap.rust_rcon_custom_commands = [
            RustRconCustomCommandRecord(
                id=1,
                name=name,
                template="status",
                binding_id=1,
                allowed_qq_ids=("123",),
            )
        ]
    service = SimpleNamespace(get_snapshot=lambda: snap)
    for module in (rcon_plugin, status_checker, live_plugin):
        monkeypatch.setattr(module, "get_config_service", lambda: service)
    monkeypatch.setattr("shared.config.service.get_config_service", lambda: service)
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    status_finish = AsyncMock(side_effect=FinishedException)
    rcon_finish = AsyncMock(side_effect=FinishedException)
    execute = AsyncMock(return_value="RCON 状态")
    monkeypatch.setattr(status_checker.status_cmd, "finish", status_finish)
    monkeypatch.setattr(live_plugin.live_status_cmd, "finish", status_finish)
    monkeypatch.setattr(rcon_plugin.rust_rcon_cmd, "finish", rcon_finish)
    monkeypatch.setattr(rcon_plugin, "execute_rcon_command", execute)
    monkeypatch.setattr(
        status_checker, "get_bot_status", AsyncMock(return_value="机器人状态")
    )
    adapter = MagicMock()
    adapter.config = SimpleNamespace(superusers=set())
    adapter.get_name.return_value = "OneBot V11"
    bot = Bot(adapter, "999")
    event = GroupMessageEvent(
        time=0,
        self_id=999,
        post_type="message",
        sub_type="normal",
        message_type="group",
        message_id=1,
        user_id=123,
        group_id=456,
        message=Message(text),
        original_message=Message(text),
        raw_message=text,
        font=0,
        sender={"user_id": 123},
        to_me=True,
    )
    for index, (prefixes, expected) in enumerate(
        ((old_prefixes, old_rcon), (new_prefixes, new_rcon))
    ):
        snap.command_extra_prefixes = prefixes
        if edit_alias:
            snap.command_aliases = normalize_command_aliases(
                {
                    cid: {
                        "enabled": cid == "live_status",
                        "triggers": ["live" if index == 0 else "!server"],
                    }
                    for cid in COMMAND_DEFAULTS
                }
            )
        status_finish.reset_mock()
        rcon_finish.reset_mock()
        execute.reset_mock()
        await _run(
            live_plugin.handle_live_status
            if edit_alias
            else status_checker.handle_status_command,
            bot,
            event,
        )
        await _run(rcon_plugin.handle_rust_rcon, bot, event)
        assert status_finish.await_count == (index if edit_alias else 1)
        assert rcon_finish.await_count == int(expected)
        assert execute.await_count == int(expected and (custom or " " in text))
        if execute.await_count:
            assert execute.await_args.args[-1] == "status"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind, title_expected",
    [
        ("enabled", True),
        ("group_disabled", False),
        ("alias_disabled", False),
        ("at_trigger", True),
        ("at_before", False),
        ("prefix_space", False),
        ("newline", False),
    ],
)
async def test_title_argument_does_not_trigger_status_fuzzy(
    monkeypatch, kind, title_expected
):
    import plugins.group_special_title as title_plugin
    from plugins.group_special_title import handler as title_handler
    from plugins.status_check import status_checker

    aliases = normalize_command_aliases(
        {
            "group_special_title": {
                "enabled": kind != "alias_disabled",
                "triggers": ["头衔"],
            }
        }
    )
    assert validation_error(aliases) is None
    snap = _command_snapshot(aliases)
    snap.group_special_title_enabled_group_ids = (
        [] if kind == "group_disabled" else ["456"]
    )
    service = SimpleNamespace(get_snapshot=lambda: snap)
    for module in (title_plugin, title_handler, status_checker):
        monkeypatch.setattr(module, "get_config_service", lambda: service)
    monkeypatch.setattr(
        title_handler, "_bot_group_role", AsyncMock(return_value="owner")
    )
    monkeypatch.setattr(
        title_handler, "try_consume_daily_quota", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        status_checker, "get_bot_status", AsyncMock(return_value="状态")
    )
    finish = AsyncMock(side_effect=FinishedException)
    monkeypatch.setattr(status_checker.status_cmd, "finish", finish)
    message = "/头衔 status"
    if kind == "at_trigger":
        message = Message(
            MessageSegment.text("/")
            + MessageSegment("at", {"qq": "42", "name": "头衔"})
            + MessageSegment.text(" status")
        )
    elif kind == "at_before":
        message = Message(
            MessageSegment("at", {"qq": "42", "name": "other"})
            + MessageSegment.text("/头衔 status")
        )
    elif kind == "prefix_space":
        message = "/ 头衔 status"
    elif kind == "newline":
        message = "/头衔 status\nXstatus"
    event, bot = _event(message), _actor()
    bot.set_group_special_title = AsyncMock()
    assert await title_plugin.group_title_cmd.rule(bot, event, {}) == title_expected
    await _run(status_checker.handle_status_command, bot, event)
    await title_handler.handle_group_special_title(bot, event)
    assert bot.set_group_special_title.await_count == int(title_expected)
    assert finish.await_count == int(not title_expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("subscribed", [False, True])
@pytest.mark.parametrize("literal", [False, True])
@pytest.mark.parametrize("scope", ["onebot-group", "onebot-private"])
@pytest.mark.parametrize("self_sender", [False, True])
async def test_extract_argument_and_whole_status_alias_have_one_owner(
    monkeypatch, subscribed, literal, scope, self_sender
):
    from plugins.dynamic_monitor import dynamic_extract as extract
    from plugins.status_check import status_checker

    text = "/提取1234567890"
    aliases = normalize_command_aliases(
        {"status": {"triggers": [text if literal else "1234567890"]}}
    )
    assert validation_error(aliases) is None
    snap = _command_snapshot(aliases)
    if subscribed:
        snap.dynamic_subscription_mapping = {"42": ["456"]}
        snap.dynamic_subscription_user_mapping = {"42": ["123"]}
    service = SimpleNamespace(get_snapshot=lambda: snap)
    monkeypatch.setattr(extract, "get_config_service", lambda: service)
    monkeypatch.setattr(status_checker, "get_config_service", lambda: service)
    monkeypatch.setattr(
        status_checker, "get_bot_status", AsyncMock(return_value="状态")
    )
    monkeypatch.setattr(
        extract.Config,
        "from_service",
        lambda: SimpleNamespace(
            bilibili_cookie="", message_templates=snap.dynamic_message_templates
        ),
    )
    monkeypatch.setattr(extract, "_fetch_dynamic_images", AsyncMock(return_value=[]))
    send, finish = AsyncMock(), AsyncMock(side_effect=FinishedException)
    monkeypatch.setattr(extract, "_send_reply", send)
    monkeypatch.setattr(status_checker.status_cmd, "finish", finish)
    event, bot = _event(text, scope), _actor()
    if self_sender:
        bot.self_id = "123"
    await _run(status_checker.handle_status_command, bot, event)
    await extract._handle_extract(bot, event)
    extraction_expected = (
        subscribed and not literal and (scope == "onebot-private" or not self_sender)
    )
    assert send.await_count == int(extraction_expected)
    assert finish.await_count == int(
        literal or (not extraction_expected and scope == "onebot-group")
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name, enabled",
    [("status", True), ("我的积分", True), ("AK  status", True), ("status", False)],
)
async def test_redeem_free_tail_is_not_a_separate_fuzzy_command(
    monkeypatch, name, enabled
):
    import plugins.rust_player as rust_player
    from plugins.status_check import status_checker

    snap = _command_snapshot(normalize_command_aliases({}))
    snap.rust_rcon_group_policies[
        "456"
    ].__dict__  # frozen record; replace when disabled
    if not enabled:
        snap.rust_rcon_group_policies = {}
    service = SimpleNamespace(get_snapshot=lambda: snap)
    monkeypatch.setattr(rust_player, "get_config_service", lambda: service)
    monkeypatch.setattr(status_checker, "get_config_service", lambda: service)
    monkeypatch.setattr(
        status_checker, "get_bot_status", AsyncMock(return_value="状态")
    )
    finish = AsyncMock(side_effect=FinishedException)
    redeem, points = AsyncMock(), AsyncMock()
    monkeypatch.setattr(status_checker.status_cmd, "finish", finish)
    monkeypatch.setattr(rust_player, "_handle_shop_redeem", redeem)
    monkeypatch.setattr(rust_player, "_handle_points_query", points)
    event, bot = _event("兑换商品 " + name), _actor()
    await _run(status_checker.handle_status_command, bot, event)
    await rust_player.handle_rust_player(bot, event)
    assert redeem.await_count == int(enabled)
    if enabled:
        assert redeem.await_args.args[2] == name
    points.assert_not_awaited()
    assert finish.await_count == int(not enabled)


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["live", "bind", "shop_list"])
async def test_other_explicit_argument_routes_keep_their_tail(monkeypatch, command):
    import plugins.live_monitor as live_plugin
    import plugins.rust_player as rust_player
    from plugins.status_check import status_checker

    aliases = normalize_command_aliases(
        {"status": {"triggers": ["1"]}} if command == "shop_list" else {}
    )
    snap = _command_snapshot(aliases)
    service = SimpleNamespace(get_snapshot=lambda: snap)
    for module in (live_plugin, rust_player, status_checker):
        monkeypatch.setattr(module, "get_config_service", lambda: service)
    monkeypatch.setattr(
        status_checker, "get_bot_status", AsyncMock(return_value="状态")
    )
    status_finish = AsyncMock(side_effect=FinishedException)
    monkeypatch.setattr(status_checker.status_cmd, "finish", status_finish)
    consume = AsyncMock(side_effect=FinishedException)
    if command == "live":
        monkeypatch.setattr(live_plugin.live_status_cmd, "finish", consume)
        text, handler = "/直播状态 status", live_plugin.handle_live_status
    elif command == "bind":
        monkeypatch.setattr(rust_player.rust_player_cmd, "finish", consume)
        text, handler = "/绑定 status", rust_player.handle_rust_player
    else:
        monkeypatch.setattr(rust_player, "_handle_shop_list", consume)
        text, handler = "/商品列表1", rust_player.handle_rust_player
    event, bot = _event(text), _actor()
    await _run(status_checker.handle_status_command, bot, event)
    await _run(handler, bot, event)
    status_finish.assert_not_awaited()
    consume.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("extra_title_alias", [False, True])
async def test_actual_extract_trigger_beats_less_specific_title(
    monkeypatch, extra_title_alias
):
    import plugins.group_special_title as title_plugin
    from plugins.dynamic_monitor import dynamic_extract as extract
    from shared.config.command_aliases import command_aliases_for_event

    title_triggers = ["头衔"] + (
        ["一个完全不匹配但比提取触发词更长的头衔触发词"] if extra_title_alias else []
    )
    aliases = normalize_command_aliases(
        {
            "dynamic_extract": {"triggers": ["头衔 status"]},
            "group_special_title": {"triggers": title_triggers},
        }
    )
    assert validation_error(aliases) is None
    snap = _command_snapshot(aliases)
    snap.group_special_title_enabled_group_ids = ["456"]
    snap.dynamic_subscription_mapping = {"42": ["456"]}
    service = SimpleNamespace(get_snapshot=lambda: snap)
    monkeypatch.setattr(extract, "get_config_service", lambda: service)
    monkeypatch.setattr(title_plugin, "get_config_service", lambda: service)
    monkeypatch.setattr(
        extract.Config,
        "from_service",
        lambda: SimpleNamespace(
            bilibili_cookie="", message_templates=snap.dynamic_message_templates
        ),
    )
    monkeypatch.setattr(extract, "_fetch_dynamic_images", AsyncMock(return_value=[]))
    send = AsyncMock()
    monkeypatch.setattr(extract, "_send_reply", send)
    event, bot = _event("/头衔 status1234567890"), _actor()
    scoped = await command_aliases_for_event(snap, bot, event)
    assert (
        scoped["dynamic_extract"].enabled and not scoped["group_special_title"].enabled
    )
    assert not await title_plugin.group_title_cmd.rule(bot, event, {})
    await extract._handle_extract(bot, event)
    send.assert_awaited_once()


@pytest.mark.asyncio
async def test_actual_raw_candidate_trigger_outranks_unused_stripped_alias(monkeypatch):
    import plugins.live_monitor as live_plugin
    import plugins.rust_player as rust_player

    aliases = normalize_command_aliases(
        {
            "live_status": {"triggers": ["/", "a status"]},
            "rust_player_shop_redeem": {"triggers": ["/ a"]},
        }
    )
    assert validation_error(aliases) is None
    snap = _command_snapshot(aliases)
    service = SimpleNamespace(get_snapshot=lambda: snap)
    for module in (live_plugin, rust_player):
        monkeypatch.setattr(module, "get_config_service", lambda: service)
    finish = AsyncMock(side_effect=FinishedException)
    redeem = AsyncMock()
    monkeypatch.setattr(live_plugin.live_status_cmd, "finish", finish)
    monkeypatch.setattr(rust_player, "_handle_shop_redeem", redeem)
    event, bot = _event("/ a status"), _actor()
    await _run(live_plugin.handle_live_status, bot, event)
    await rust_player.handle_rust_player(bot, event)
    finish.assert_not_awaited()
    redeem.assert_awaited_once()


@pytest.mark.asyncio
async def test_whole_points_alias_owns_title_input_and_its_rule(monkeypatch):
    import plugins.group_special_title as title_plugin
    import plugins.rust_player as rust_player

    aliases = normalize_command_aliases(
        {"rust_player_points": {"triggers": ["/头衔 status"]}}
    )
    assert validation_error(aliases) is None
    snap = _command_snapshot(aliases)
    snap.group_special_title_enabled_group_ids = ["456"]
    service = SimpleNamespace(get_snapshot=lambda: snap)
    for module in (title_plugin, rust_player):
        monkeypatch.setattr(module, "get_config_service", lambda: service)
    points = AsyncMock()
    monkeypatch.setattr(rust_player, "_handle_points_query", points)
    event, bot = _event("/头衔 status"), _actor()
    assert not await title_plugin.group_title_cmd.rule(bot, event, {})
    await rust_player.handle_rust_player(bot, event)
    points.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text, status_trigger",
    [
        ("/提取 1234567890", "1234567890"),
        ("/提取123456789", "123456789"),
        ("/兑换商品 status 0", "0"),
        ("/商品列表0", "0"),
        ("最新视频 status", "status"),
    ],
)
async def test_incomplete_argument_grammar_does_not_swallow_fuzzy(text, status_trigger):
    from shared.config.command_aliases import command_aliases_for_event, match_plain

    aliases = normalize_command_aliases({"status": {"triggers": [status_trigger]}})
    snap = _command_snapshot(aliases)
    snap.dynamic_subscription_mapping = {"42": ["456"]}
    snap.group_special_title_enabled_group_ids = ["456"]
    event, bot = _event(text), _actor()
    scoped = await command_aliases_for_event(snap, bot, event)
    assert match_plain(event.get_plaintext(), "status", scoped, is_tome=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mentioned,list_trigger,list_enabled,expected",
    [
        (False, "/status", True, "live"),
        (True, "/status", True, "list"),
        (False, "/status 12345", True, "list"),
        (True, "/status 12345", True, "list"),
        (False, "/status", False, "live"),
    ],
)
async def test_partial_list_head_does_not_hide_live_room_query(
    monkeypatch, mentioned, list_trigger, list_enabled, expected
):
    import plugins.live_monitor as live_plugin
    from plugins.live_monitor import live_monitor as live_mod

    aliases = normalize_command_aliases(
        {
            "live_status": {"triggers": ["status"]},
            "live_monitor_list": {"enabled": list_enabled, "triggers": [list_trigger]},
        }
    )
    snap = _command_snapshot(aliases)
    service = SimpleNamespace(get_snapshot=lambda: snap)
    monkeypatch.setattr(live_plugin, "get_config_service", lambda: service)
    monkeypatch.setattr(
        live_plugin.Config,
        "from_service",
        lambda: SimpleNamespace(live_monitor_mapping={}),
    )
    check = AsyncMock(
        return_value={
            "room_id": 12345,
            "streamer_name": "测试主播",
            "title": "测试标题",
            "is_living": False,
        }
    )
    monkeypatch.setattr(
        live_mod, "live_monitor_instance", SimpleNamespace(check_room_now=check)
    )
    live_finish, list_finish = (
        AsyncMock(side_effect=FinishedException),
        AsyncMock(side_effect=FinishedException),
    )
    monkeypatch.setattr(live_plugin.live_status_cmd, "finish", live_finish)
    monkeypatch.setattr(live_plugin.live_status_cmd, "send", AsyncMock())
    monkeypatch.setattr(live_plugin.list_monitor_cmd, "finish", list_finish)
    event, bot = _event("/status 12345"), _actor()
    event.is_tome.return_value = mentioned
    await _run(live_plugin.handle_live_status, bot, event)
    await _run(live_plugin.handle_list_monitor, bot, event)
    if expected == "live":
        check.assert_awaited_once_with("12345")
        live_finish.assert_awaited_once()
        list_finish.assert_not_awaited()
    else:
        check.assert_not_awaited()
        live_finish.assert_not_awaited()
        list_finish.assert_awaited_once()


@pytest.mark.asyncio
async def test_more_specific_actual_argument_trigger_owns_legacy_overlap():
    from shared.config.command_aliases import command_aliases_for_event

    aliases = normalize_command_aliases(
        {
            "live_status": {"triggers": ["查询"]},
            "rust_player_bind": {"triggers": ["/查询"]},
        }
    )
    snap = _command_snapshot(aliases)
    scoped = await command_aliases_for_event(snap, _actor(), _event("/查询 12345"))
    assert scoped["rust_player_bind"].enabled
    assert not scoped["live_status"].enabled
