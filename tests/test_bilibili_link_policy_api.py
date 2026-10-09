"""Bilibili leaf-policy APIs must only mutate known editable targets."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import nonebot
import pytest
from fastapi import HTTPException

from admin.schemas.link_parser import (
    LinkParserGroupPolicyUpdateRequest,
    LinkParserUserPolicyCreateRequest,
    LinkParserUserPolicyUpdateRequest,
)
from shared.config.link_parser_policy import (
    LinkParserGroupPolicyRecord,
    LinkParserUserPolicyRecord,
)
from shared.config.types import AppConfigSnapshot


@pytest.fixture
def policy_api(monkeypatch):
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(sqlalchemy_database_url="sqlite+aiosqlite:///:memory:")
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")
    from admin.api.v1 import link_parser as api

    snapshot = AppConfigSnapshot(
        message_enabled_group_ids=["official", "1001", "unknown"],
        message_enabled_user_ids=["official", "1001", "unknown", "9999"],
        link_parser_user_policies={
            "9999": LinkParserUserPolicyRecord(user_id="9999", live_enabled=True),
            "unknown": LinkParserUserPolicyRecord(user_id="unknown", live_enabled=True),
        },
    )
    service = SimpleNamespace(get_snapshot=lambda: snapshot, reload=AsyncMock())

    async def upsert_group(group_id, **flags):
        snapshot.link_parser_group_policies[group_id] = LinkParserGroupPolicyRecord(
            group_id=group_id, **flags
        )

    async def upsert_user(user_id, **flags):
        snapshot.link_parser_user_policies[user_id] = LinkParserUserPolicyRecord(
            user_id=user_id, **flags
        )

    service.upsert_link_parser_group_policy = AsyncMock(side_effect=upsert_group)
    service.upsert_link_parser_user_policy = AsyncMock(side_effect=upsert_user)
    service.delete_link_parser_group_policy = AsyncMock(
        side_effect=lambda target: snapshot.link_parser_group_policies.pop(target, None)
    )
    service.delete_link_parser_user_policy = AsyncMock(
        side_effect=lambda target: snapshot.link_parser_user_policies.pop(target, None)
    )
    monkeypatch.setattr(api, "get_config_service", lambda: service)
    return api, snapshot, service


def _roster(api, monkeypatch, scope, status):
    key = "group_id" if scope == "group" else "user_id"
    fetch = AsyncMock(
        return_value=(
            [
                {key: "official", "source": "official"},
                {key: "1001", "source": "onebot"},
                {key: "disabled", "source": "official"},
            ],
            status,
        )
    )
    monkeypatch.setattr(
        api,
        "get_group_list_with_status"
        if scope == "group"
        else "get_friend_list_with_availability",
        fetch,
    )
    return fetch


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "user"])
@pytest.mark.parametrize("status", ["ok", "offline", "incomplete"])
async def test_lists_and_mutations_keep_official_targets_editable(
    scope, status, policy_api, monkeypatch
):
    api, _, service = policy_api
    fetch = _roster(api, monkeypatch, scope, status)
    listing = api.list_group_policies if scope == "group" else api.list_user_policies
    response = await listing(None)
    assert response.onebot_list_status == status
    assert (
        response.group_list_available
        if scope == "group"
        else response.friend_list_available
    ) is (status == "ok")
    rows = response.groups if scope == "group" else response.users
    official = next(row for row in rows if getattr(row, f"{scope}_id") == "official")
    assert official.source == "official" and official.editable
    assert not official.customized and not official.video_enabled
    assert all(
        getattr(row, f"{scope}_id") not in {"disabled", "unknown"} for row in rows
    )
    numeric = next((row for row in rows if getattr(row, f"{scope}_id") == "1001"), None)
    assert (numeric is None) is (status == "offline")
    if numeric:
        assert numeric.editable is (status == "ok")
    if scope == "group":
        body = LinkParserGroupPolicyUpdateRequest(
            video_enabled=True,
            live_enabled=True,
            dynamic_enabled=True,
            send_video_enabled=True,
        )
        update, reset = api.update_group_policy, api.reset_group_policy
    else:
        body = LinkParserUserPolicyUpdateRequest(
            video_enabled=True,
            live_enabled=True,
            dynamic_enabled=True,
            send_video_enabled=True,
        )
        update, reset = api.update_user_policy, api.reset_user_policy
    fetch.reset_mock()
    enabled = await update("official", body, None)
    assert (
        enabled.item.source == "official"
        and enabled.item.editable
        and enabled.item.customized
    )
    assert enabled.item.send_video_enabled
    fetch.assert_awaited_once()
    cleared = await reset("official", None)
    assert cleared.item.source == "official" and cleared.item.editable
    assert not cleared.item.customized and not cleared.item.video_enabled
    assert service.reload.await_count == 2
    assert service.get_snapshot().link_parser_user_policies["9999"].live_enabled


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "user"])
@pytest.mark.parametrize(
    "status,target",
    [
        ("offline", "1001"),
        ("incomplete", "1001"),
        ("offline", "unknown"),
        ("incomplete", "unknown"),
        ("ok", "unknown"),
    ],
)
@pytest.mark.parametrize("operation", ["update", "reset"])
async def test_unknown_or_readonly_targets_cannot_mutate(
    scope, status, target, operation, policy_api, monkeypatch
):
    api, _, service = policy_api
    _roster(api, monkeypatch, scope, status)
    if operation == "update":
        body_cls = (
            LinkParserGroupPolicyUpdateRequest
            if scope == "group"
            else LinkParserUserPolicyUpdateRequest
        )
        body = body_cls(video_enabled=True, live_enabled=False, dynamic_enabled=False)
        call = api.update_group_policy if scope == "group" else api.update_user_policy
        args = (target, body, None)
    else:
        call = api.reset_group_policy if scope == "group" else api.reset_user_policy
        args = (target, None)
    with pytest.raises(HTTPException) as error:
        await call(*args)
    assert error.value.status_code == 503
    service.reload.assert_not_awaited()
    service.upsert_link_parser_group_policy.assert_not_awaited()
    service.upsert_link_parser_user_policy.assert_not_awaited()
    service.delete_link_parser_group_policy.assert_not_awaited()
    service.delete_link_parser_user_policy.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "user"])
@pytest.mark.parametrize("operation", ["update", "reset"])
async def test_master_disabled_target_cannot_change_leaf_policy(
    scope, operation, policy_api, monkeypatch
):
    api, snapshot, service = policy_api
    _roster(api, monkeypatch, scope, "offline")
    snapshot.message_enabled_group_ids.clear()
    snapshot.message_enabled_user_ids.clear()
    if operation == "update":
        body_cls = (
            LinkParserGroupPolicyUpdateRequest
            if scope == "group"
            else LinkParserUserPolicyUpdateRequest
        )
        call = api.update_group_policy if scope == "group" else api.update_user_policy
        args = (
            "official",
            body_cls(video_enabled=True, live_enabled=False, dynamic_enabled=False),
            None,
        )
    else:
        call = api.reset_group_policy if scope == "group" else api.reset_user_policy
        args = ("official", None)
    with pytest.raises(HTTPException) as error:
        await call(*args)
    assert error.value.status_code == 400
    service.reload.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["ok", "offline", "incomplete"])
@pytest.mark.parametrize("target", ["official", "unknown", "1001"])
async def test_create_user_only_accepts_known_official_or_complete_numeric(
    status, target, policy_api, monkeypatch
):
    api, snapshot, service = policy_api
    snapshot.link_parser_user_policies.clear()
    _roster(api, monkeypatch, "user", status)
    body = LinkParserUserPolicyCreateRequest(user_id=target, video_enabled=True)
    if target == "official" or target == "1001" and status == "ok":
        response = await api.create_user_policy(body, None)
        assert response.item.video_enabled
        assert response.item.source == (
            "official" if target == "official" else "onebot"
        )
    else:
        with pytest.raises(HTTPException) as error:
            await api.create_user_policy(body, None)
        assert error.value.status_code == 503
        service.upsert_link_parser_user_policy.assert_not_awaited()
