"""Douyin policy access, persistence, and native-handler config reload."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests import test_douyin_official_links
from tests.test_config_service_load_perf import _ensure_real_db_modules

native_plugin = test_douyin_official_links.native_plugin


@pytest.fixture
async def policy_api(monkeypatch):
    _ensure_real_db_modules()
    from admin.api.v1 import douyin_link_parser as api
    from shared.config import service as service_module
    from shared.db.base import Model

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(service_module, "get_session", factory)
    monkeypatch.setattr(service_module, "apply_nonebot_superusers", lambda _: None)
    svc = service_module.ConfigService()
    monkeypatch.setattr(service_module, "get_config_service", lambda: svc)
    monkeypatch.setattr(api, "get_config_service", lambda: svc)
    await svc.set_settings(
        {
            "message_enabled_group_ids": '["g-openid", "101", "999", "unknown"]',
            "message_enabled_user_ids": '["u-openid", "101", "999", "unknown"]',
        }
    )
    await svc.reload()
    try:
        yield api, svc, factory
    finally:
        await engine.dispose()


def _scope(api, scope, status, monkeypatch):
    is_group = scope == "group"
    target = "g-openid" if is_group else "u-openid"
    key = "group_id" if is_group else "user_id"
    rows = [
        {key: target, "source": "official"},
        {key: "101", "source": "onebot"},
        {key: "disabled", "source": "official"},
    ]
    fetch = AsyncMock(return_value=(rows, status))
    monkeypatch.setattr(
        api,
        "get_group_list_with_status"
        if is_group
        else "get_friend_list_with_availability",
        fetch,
    )
    return target, fetch


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "user"])
@pytest.mark.parametrize("status", ["ok", "offline", "incomplete"])
async def test_policy_list_shows_known_official_rows_without_complete_onebot(
    scope, status, policy_api, monkeypatch
):
    api, svc, _ = policy_api
    target, fetch = _scope(api, scope, status, monkeypatch)
    if scope == "user":
        await svc.upsert_douyin_link_parser_user_policy("999", enabled=True)
        await svc.upsert_douyin_link_parser_user_policy("unknown", enabled=True)
        await svc.reload()
    response = await (
        api.list_group_policies(None)
        if scope == "group"
        else api.list_user_policies(None)
    )
    items = response.groups if scope == "group" else response.users
    by_id = {
        item.group_id if scope == "group" else item.user_id: item for item in items
    }
    expected = {target}
    if status != "offline":
        expected.add("101")
    if scope == "user" and status == "ok":
        expected.add("999")
    assert set(by_id) == expected
    assert by_id[target].source == "official"
    assert by_id[target].editable and not by_id[target].enabled
    if "101" in by_id:
        assert by_id["101"].source == "onebot"
        assert by_id["101"].editable == (status == "ok")
    assert response.onebot_list_status == status
    available = (
        response.group_list_available
        if scope == "group"
        else response.friend_list_available
    )
    assert available == (status == "ok")
    fetch.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "user"])
@pytest.mark.parametrize("status", ["ok", "offline", "incomplete"])
async def test_official_policy_enable_and_reset_persist_and_reload(
    scope, status, policy_api, monkeypatch
):
    api, svc, factory = policy_api
    from shared.db.models import DouyinLinkParserGroupPolicy, DouyinLinkParserUserPolicy

    target, fetch = _scope(api, scope, status, monkeypatch)
    callback = AsyncMock()
    svc.register_reload_callback(callback)
    if scope == "group":
        response = await api.update_group_policy(
            target, api.DouyinLinkParserGroupPolicyUpdateRequest(enabled=True), None
        )
        model = DouyinLinkParserGroupPolicy
    else:
        response = await api.update_user_policy(
            target, api.DouyinLinkParserUserPolicyUpdateRequest(enabled=True), None
        )
        model = DouyinLinkParserUserPolicy
    assert response.item.enabled and response.item.customized
    assert response.item.source == "official" and response.item.editable
    async with factory() as session:
        assert (await session.get(model, target)).enabled
    callback.assert_awaited_once()
    fetch.assert_awaited_once()
    fetch.reset_mock()
    response = await (
        api.reset_group_policy(target, None)
        if scope == "group"
        else api.reset_user_policy(target, None)
    )
    assert not response.item.enabled and not response.item.customized
    async with factory() as session:
        assert await session.get(model, target) is None
    assert callback.await_count == 2
    fetch.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "user"])
@pytest.mark.parametrize("status", ["ok", "offline", "incomplete"])
@pytest.mark.parametrize("reset", [False, True])
async def test_unknown_openid_and_master_disabled_cannot_mutate(
    scope, status, reset, policy_api, monkeypatch
):
    api, svc, _ = policy_api
    _scope(api, scope, status, monkeypatch)
    for target, expected_status in (("unknown", 503), ("disabled", 400)):
        with pytest.raises(HTTPException) as caught:
            if scope == "group":
                await (
                    api.reset_group_policy(target, None)
                    if reset
                    else api.update_group_policy(
                        target,
                        api.DouyinLinkParserGroupPolicyUpdateRequest(enabled=True),
                        None,
                    )
                )
            else:
                await (
                    api.reset_user_policy(target, None)
                    if reset
                    else api.update_user_policy(
                        target,
                        api.DouyinLinkParserUserPolicyUpdateRequest(enabled=True),
                        None,
                    )
                )
        assert caught.value.status_code == expected_status
    assert not svc.get_snapshot().douyin_link_parser_group_policies
    assert not svc.get_snapshot().douyin_link_parser_user_policies


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "user"])
@pytest.mark.parametrize("status", ["offline", "incomplete"])
async def test_numeric_policy_mutations_require_complete_onebot(
    scope, status, policy_api, monkeypatch
):
    api, _, _ = policy_api
    _scope(api, scope, status, monkeypatch)
    if scope == "group":
        operations = [
            api.update_group_policy(
                "101", api.DouyinLinkParserGroupPolicyUpdateRequest(enabled=True), None
            ),
            api.reset_group_policy("101", None),
        ]
    else:
        operations = [
            api.create_user_policy(
                api.DouyinLinkParserUserPolicyCreateRequest(
                    user_id="101", enabled=True
                ),
                None,
            ),
            api.update_user_policy(
                "101", api.DouyinLinkParserUserPolicyUpdateRequest(enabled=True), None
            ),
            api.reset_user_policy("101", None),
        ]
    for operation in operations:
        with pytest.raises(HTTPException) as caught:
            await operation
        assert caught.value.status_code == 503


@pytest.mark.asyncio
async def test_complete_onebot_keeps_numeric_nonfriend_policy_creation(
    policy_api, monkeypatch
):
    api, svc, _ = policy_api
    _scope(api, "user", "ok", monkeypatch)
    response = await api.create_user_policy(
        api.DouyinLinkParserUserPolicyCreateRequest(
            user_id="999", enabled=True, name="non-friend"
        ),
        None,
    )
    assert response.item.enabled and response.item.editable
    assert response.item.source == "onebot"
    assert (
        svc.get_snapshot().douyin_link_parser_user_policies["999"].name == "non-friend"
    )
    response = await api.update_user_policy(
        "999", api.DouyinLinkParserUserPolicyUpdateRequest(enabled=False), None
    )
    assert not response.item.enabled and not response.item.customized


@pytest.mark.asyncio
async def test_official_policy_and_cookie_reload_reach_actual_native_handler(
    policy_api, native_plugin, monkeypatch
):
    api, svc, _ = policy_api
    from nonebot.adapters.qq.event import C2CMessageCreateEvent

    _scope(api, "user", "offline", monkeypatch)
    native_plugin._register_config_reload()
    event = C2CMessageCreateEvent.model_validate(
        {
            "id": "incoming",
            "timestamp": "2026-10-09T00:00:00Z",
            "content": "https://www.douyin.com/video/200",
            "author": {"id": "u-openid", "user_openid": "u-openid", "bot": False},
        }
    )
    reply = AsyncMock()
    monkeypatch.setattr(native_plugin, "_download_and_reply", reply)
    bot = SimpleNamespace(self_id="app")
    await native_plugin.handle_private_douyin_link(bot, event)
    reply.assert_not_awaited()
    await api.update_user_policy(
        "u-openid", api.DouyinLinkParserUserPolicyUpdateRequest(enabled=True), None
    )
    await api.save_cookie(api.DouyinCookieSaveRequest(cookie="ttwid=test-only"), None)
    await native_plugin.handle_private_douyin_link(bot, event)
    assert reply.await_args.args[2].douyin_cookie == "ttwid=test-only"
    await api.clear_cookie(None)
    await native_plugin.handle_private_douyin_link(bot, event)
    assert reply.await_args.args[2].douyin_cookie == ""
    await api.reset_user_policy("u-openid", None)
    reply.reset_mock()
    await native_plugin.handle_private_douyin_link(bot, event)
    reply.assert_not_awaited()
