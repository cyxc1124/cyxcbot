"""X leaf-policy access and persistence on mixed QQ adapters."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from nonebot.adapters.qq import Bot as QQBot
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shared.adapter.official_runtime import _bot_info
from shared.config.types import AppConfigSnapshot
from shared.config.x_link_parser_policy import (
    XLinkParserGroupPolicyRecord,
    XLinkParserUserPolicyRecord,
    resolve_x_link_parser_policy,
)
from shared.security.crypto import encrypt_value
from tests.test_config_service_load_perf import _ensure_real_db_modules
from tests.test_x_official_links import _event
from tests.test_x_official_links import plugin as plugin
from utils.x_api.models import TweetItem


@pytest.fixture
def api(monkeypatch):
    _ensure_real_db_modules()
    from admin.api.v1 import x_link_parser

    monkeypatch.setattr(x_link_parser, "invalidate_user_list_cache", lambda: None)
    return x_link_parser


def _snapshot():
    return AppConfigSnapshot(
        message_enabled_group_ids=["100", "g-openid", "unknown"],
        message_enabled_user_ids=["100", "u-openid", "unknown"],
        x_link_parser_group_policies={
            "100": XLinkParserGroupPolicyRecord("100", True),
        },
        x_link_parser_user_policies={
            "100": XLinkParserUserPolicyRecord("100", True),
            "unknown": XLinkParserUserPolicyRecord("unknown", True),
        },
    )


@pytest.mark.parametrize("scope", ["group", "user"])
@pytest.mark.parametrize("fetch_status", ["offline", "incomplete", "ok"])
async def test_list_keeps_official_cache_and_roster_completeness(
    api, monkeypatch, scope, fetch_status
):
    snap = _snapshot()
    id_key = "group_id" if scope == "group" else "user_id"
    openid = "g-openid" if scope == "group" else "u-openid"
    rows = [
        {id_key: "100", "source": "onebot"},
        {id_key: openid, "source": "official"},
        {id_key: "disabled", "source": "official"},
    ]
    monkeypatch.setattr(api, "get_config_service", lambda: _Service(snap))
    monkeypatch.setattr(
        api,
        "get_group_list_with_status"
        if scope == "group"
        else "get_friend_list_with_availability",
        AsyncMock(return_value=(rows, fetch_status)),
    )
    response = await (
        api.list_group_policies(None)
        if scope == "group"
        else api.list_user_policies(None)
    )
    items = response.groups if scope == "group" else response.users
    by_id = {getattr(item, id_key): item for item in items}
    assert set(by_id) == ({openid} if fetch_status == "offline" else {"100", openid})
    assert by_id[openid].source == "official"
    assert by_id[openid].editable is True
    assert by_id[openid].enabled is False
    if "100" in by_id:
        assert by_id["100"].editable is (fetch_status == "ok")
    available = (
        response.group_list_available
        if scope == "group"
        else response.friend_list_available
    )
    assert available is (fetch_status == "ok")
    assert response.onebot_list_status == fetch_status


class _Service:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.upsert_x_link_parser_group_policy = AsyncMock()
        self.upsert_x_link_parser_user_policy = AsyncMock()
        self.delete_x_link_parser_group_policy = AsyncMock()
        self.delete_x_link_parser_user_policy = AsyncMock()
        self.reload = AsyncMock()

    def get_snapshot(self):
        return self.snapshot


@pytest.mark.parametrize("scope", ["group", "user"])
@pytest.mark.parametrize(
    ("fetch_status", "target_id"),
    [
        ("offline", "100"),
        ("incomplete", "100"),
        ("offline", "unknown"),
        ("incomplete", "unknown"),
        ("ok", "unknown"),
    ],
)
@pytest.mark.parametrize("reset", [False, True])
async def test_mutation_rejects_incomplete_numeric_and_unknown_openids(
    api, monkeypatch, scope, fetch_status, target_id, reset
):
    svc = _Service(_snapshot())
    id_key = "group_id" if scope == "group" else "user_id"
    fetch = AsyncMock(return_value=([{id_key: "100"}], fetch_status))
    monkeypatch.setattr(api, "get_config_service", lambda: svc)
    monkeypatch.setattr(
        api,
        "get_group_list_with_status"
        if scope == "group"
        else "get_friend_list_with_availability",
        fetch,
    )
    mutate = (
        (api.reset_group_policy if scope == "group" else api.reset_user_policy)
        if reset
        else (api.update_group_policy if scope == "group" else api.update_user_policy)
    )
    args = (
        (target_id, None)
        if reset
        else (
            target_id,
            api.XLinkParserGroupPolicyUpdateRequest(enabled=True)
            if scope == "group"
            else api.XLinkParserUserPolicyUpdateRequest(enabled=True),
            None,
        )
    )
    with pytest.raises(HTTPException) as exc:
        await mutate(*args)
    assert exc.value.status_code == 503
    fetch.assert_awaited_once()
    svc.upsert_x_link_parser_group_policy.assert_not_awaited()
    svc.upsert_x_link_parser_user_policy.assert_not_awaited()
    svc.delete_x_link_parser_group_policy.assert_not_awaited()
    svc.delete_x_link_parser_user_policy.assert_not_awaited()
    svc.reload.assert_not_awaited()


@pytest.fixture
async def persisted_service(api, monkeypatch, tmp_path):
    from shared.config import service
    from shared.db.base import Model

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'x-policies.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(service, "get_session", factory)
    svc = service.ConfigService()
    await svc.set_settings(
        {
            "message_enabled_group_ids": '["g-openid", "100"]',
            "message_enabled_user_ids": '["u-openid", "100"]',
            "x_api_bearer_encrypted": encrypt_value("test-bearer"),
        }
    )
    await svc.load()
    monkeypatch.setattr(api, "get_config_service", lambda: svc)
    try:
        yield svc, factory
    finally:
        await engine.dispose()


@pytest.mark.parametrize("scope", ["group", "user"])
@pytest.mark.parametrize("fetch_status", ["offline", "incomplete"])
async def test_cached_official_enable_reset_persists_and_reloads(
    api, monkeypatch, persisted_service, plugin, scope, fetch_status
):
    from shared.db.models import XLinkParserGroupPolicy, XLinkParserUserPolicy

    svc, factory = persisted_service
    monkeypatch.setattr(plugin, "get_config_service", lambda: svc)
    monkeypatch.setattr("shared.config.service.get_config_service", lambda: svc)
    svc.register_reload_callback(plugin._on_config_reload)
    http_session = SimpleNamespace(close=AsyncMock())
    client = SimpleNamespace(
        get_tweet_by_id=AsyncMock(
            return_value=TweetItem(
                "200",
                "caption",
                "",
                "author",
                "Author",
                "https://x.com/author/status/200",
            )
        )
    )
    monkeypatch.setattr(plugin, "create_session", lambda _: http_session)
    monkeypatch.setattr(plugin, "XApiClient", lambda *_: client)
    monkeypatch.setattr(plugin, "materialize_tweet_media", AsyncMock(return_value=[]))
    bot = QQBot(MagicMock(), "app", _bot_info("app", "secret", False))
    send = AsyncMock()
    monkeypatch.setattr(
        bot, "send_to_group" if scope == "group" else "send_to_c2c", send
    )
    handler = (
        plugin.handle_group_x_link if scope == "group" else plugin.handle_private_x_link
    )
    id_key = "group_id" if scope == "group" else "user_id"
    target_id = "g-openid" if scope == "group" else "u-openid"
    fetch = AsyncMock(
        return_value=([{id_key: target_id, "source": "official"}], fetch_status)
    )
    monkeypatch.setattr(
        api,
        "get_group_list_with_status"
        if scope == "group"
        else "get_friend_list_with_availability",
        fetch,
    )
    callback = AsyncMock()
    svc.register_reload_callback(callback)
    update = api.update_group_policy if scope == "group" else api.update_user_policy
    body = (
        api.XLinkParserGroupPolicyUpdateRequest(enabled=True)
        if scope == "group"
        else api.XLinkParserUserPolicyUpdateRequest(enabled=True)
    )
    response = await update(target_id, body, None)
    assert response.item.enabled and response.item.editable
    assert response.item.source == "official"
    fetch.assert_awaited_once()
    callback.assert_awaited_once_with(svc.get_snapshot())
    assert plugin.get_config().x_api_bearer == "test-bearer"
    await handler(bot, _event("group" if scope == "group" else "c2c"))
    client.get_tweet_by_id.assert_awaited_once_with("200")
    send.assert_awaited_once()
    assert resolve_x_link_parser_policy(
        svc.get_snapshot(),
        group_id=target_id if scope == "group" else None,
        user_id=target_id if scope == "user" else None,
        is_private=scope == "user",
    ).enabled
    model = XLinkParserGroupPolicy if scope == "group" else XLinkParserUserPolicy
    async with factory() as session:
        assert (await session.get(model, target_id)).enabled
    reset = api.reset_group_policy if scope == "group" else api.reset_user_policy
    response = await reset(target_id, None)
    assert not response.item.enabled and not response.item.customized
    assert response.item.editable
    async with factory() as session:
        assert await session.get(model, target_id) is None
    assert not resolve_x_link_parser_policy(
        svc.get_snapshot(),
        group_id=target_id if scope == "group" else None,
        user_id=target_id if scope == "user" else None,
        is_private=scope == "user",
    ).enabled
    assert callback.await_count == 2
    await handler(bot, _event("group" if scope == "group" else "c2c"))
    client.get_tweet_by_id.assert_awaited_once()
    http_session.close.assert_awaited_once()


@pytest.mark.parametrize("scope", ["group", "user"])
@pytest.mark.parametrize("reset", [False, True])
async def test_official_mutation_requires_master_message_switch(
    api, monkeypatch, scope, reset
):
    target_id = "g-openid" if scope == "group" else "u-openid"
    id_key = "group_id" if scope == "group" else "user_id"
    svc = _Service(AppConfigSnapshot())
    monkeypatch.setattr(api, "get_config_service", lambda: svc)
    monkeypatch.setattr(
        api,
        "get_group_list_with_status"
        if scope == "group"
        else "get_friend_list_with_availability",
        AsyncMock(
            return_value=([{id_key: target_id, "source": "official"}], "offline")
        ),
    )
    mutate = (
        (api.reset_group_policy if scope == "group" else api.reset_user_policy)
        if reset
        else (api.update_group_policy if scope == "group" else api.update_user_policy)
    )
    args = (
        (target_id, None)
        if reset
        else (
            target_id,
            api.XLinkParserGroupPolicyUpdateRequest(enabled=True)
            if scope == "group"
            else api.XLinkParserUserPolicyUpdateRequest(enabled=True),
            None,
        )
    )
    with pytest.raises(HTTPException) as exc:
        await mutate(*args)
    assert exc.value.status_code == 400
    svc.reload.assert_not_awaited()


async def test_complete_onebot_preserves_numeric_nonfriend_creation(
    api, monkeypatch, persisted_service
):
    monkeypatch.setattr(
        api, "get_friend_list_with_availability", AsyncMock(return_value=([], "ok"))
    )
    response = await api.create_user_policy(
        api.XLinkParserUserPolicyCreateRequest(
            user_id="100", enabled=True, name="QQ user"
        ),
        None,
    )
    assert response.item.enabled and response.item.editable
    assert response.item.source == "onebot"
    listed = await api.list_user_policies(None)
    assert [item.user_id for item in listed.users] == ["100"]
    assert listed.friend_list_available is True


async def test_openid_cannot_be_created_directly(api):
    with pytest.raises(HTTPException) as exc:
        await api.create_user_policy(
            api.XLinkParserUserPolicyCreateRequest(user_id="unknown", enabled=True),
            None,
        )
    assert exc.value.status_code == 400
