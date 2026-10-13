"""Status policy edits must preserve unavailable OneBot allowlists."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import nonebot
import pytest
from fastapi import HTTPException

from admin.schemas.status_check import (
    GroupStatusPolicyUpdateRequest,
    PrivateStatusPolicyUpdateRequest,
)
from shared.config.types import AppConfigSnapshot


@pytest.fixture(params=["group", "private"])
def policy_api(request, monkeypatch):
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(sqlalchemy_database_url="sqlite+aiosqlite:///:memory:")
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")
    from admin.api.v1 import groups, private

    is_group = request.param == "group"
    api = groups if is_group else private
    key = "group" if is_group else "user"
    prefix = "group" if is_group else "private"
    snapshot = AppConfigSnapshot(
        message_enabled_group_ids=["official", "1001", "1002"],
        message_enabled_user_ids=["official", "1001", "1002"],
        status_check_enabled_group_ids=["1001", "hidden-official"],
        status_check_enabled_user_ids=["1001", "hidden-official"],
    )

    async def set_settings(updates):
        for field, value in updates.items():
            setattr(snapshot, field, json.loads(value))

    service = SimpleNamespace(
        get_snapshot=lambda: snapshot,
        set_settings=AsyncMock(side_effect=set_settings),
        reload=AsyncMock(),
    )
    monkeypatch.setattr(api, "get_config_service", lambda: service)
    return SimpleNamespace(
        api=api,
        key=key,
        prefix=prefix,
        snapshot=snapshot,
        service=service,
        request_type=(
            GroupStatusPolicyUpdateRequest
            if is_group
            else PrivateStatusPolicyUpdateRequest
        ),
        roster_name=(
            "get_group_list_with_status"
            if is_group
            else "get_friend_list_with_availability"
        ),
    )


def _roster(policy, monkeypatch, fetch_status):
    rows = [
        {f"{policy.key}_id": "official", "source": "official"},
        {f"{policy.key}_id": "1002", "source": "onebot"},
        {f"{policy.key}_id": "disabled", "source": "official"},
    ]
    monkeypatch.setattr(
        policy.api, policy.roster_name, AsyncMock(return_value=(rows, fetch_status))
    )


def _request(policy, enabled_ids, *, restrict=True, display=None):
    return policy.request_type(
        restrict=restrict,
        **{f"enabled_{policy.key}_ids": enabled_ids},
        display=display,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch_status", ["offline", "incomplete"])
async def test_official_toggle_preserves_hidden_ids_and_survives_reload(
    policy_api, monkeypatch, fetch_status
):
    policy = policy_api
    _roster(policy, monkeypatch, fetch_status)
    response = await policy.api.get_status_policy(None)
    rows = response.groups if policy.key == "group" else response.users
    assert [getattr(row, f"{policy.key}_id") for row in rows] == (
        ["official"] if fetch_status == "offline" else ["official", "1002"]
    )
    assert response.onebot_list_status == fetch_status
    assert getattr(response, f"enabled_{policy.key}_ids") == [
        "1001",
        "hidden-official",
    ]
    for enabled in (True, False):
        expected = ["1001", "hidden-official"] + (["official"] if enabled else [])
        response = await policy.api.update_status_policy(
            _request(policy, expected), None
        )
        assert response.restrict is True
        assert getattr(response, f"enabled_{policy.key}_ids") == expected
        response = await policy.api.get_status_policy(None)
        assert getattr(response, f"enabled_{policy.key}_ids") == expected
    assert policy.service.set_settings.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch_status", ["offline", "incomplete"])
@pytest.mark.parametrize(
    "change",
    ["global", "numeric-add", "numeric-remove", "hidden", "unknown", "disabled"],
)
async def test_partial_roster_rejects_nonvisible_or_nonofficial_changes(
    policy_api, monkeypatch, fetch_status, change
):
    policy = policy_api
    _roster(policy, monkeypatch, fetch_status)
    enabled_ids = ["1001", "hidden-official"]
    if change == "global":
        enabled_ids = []
    elif change == "numeric-remove":
        enabled_ids.remove("1001")
    elif change == "hidden":
        enabled_ids.remove("hidden-official")
    else:
        enabled_ids.append("1002" if change == "numeric-add" else change)
    with pytest.raises(HTTPException) as error:
        await policy.api.update_status_policy(
            _request(policy, enabled_ids, restrict=change != "global"), None
        )
    assert error.value.status_code == 503
    policy.service.set_settings.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch_status", ["offline", "incomplete"])
@pytest.mark.parametrize("restrict", [True, False])
async def test_display_only_save_preserves_partial_roster_policy(
    policy_api, monkeypatch, fetch_status, restrict
):
    policy = policy_api
    _roster(policy, monkeypatch, fetch_status)
    setattr(policy.snapshot, f"status_check_{policy.prefix}_restrict", restrict)
    response = await policy.api.update_status_policy(
        _request(
            policy,
            ["hidden-official", "1001"],
            restrict=restrict,
            display={"show_detailed": False, "show_uptime": True, "show_memory": False},
        ),
        None,
    )
    assert response.restrict is restrict
    assert getattr(response, f"enabled_{policy.key}_ids") == [
        "1001",
        "hidden-official",
    ]
    assert response.display.model_dump() == {
        "show_detailed": False,
        "show_uptime": True,
        "show_memory": False,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch_status", ["offline", "incomplete"])
async def test_global_mode_cannot_be_changed_with_partial_roster(
    policy_api, monkeypatch, fetch_status
):
    policy = policy_api
    _roster(policy, monkeypatch, fetch_status)
    setattr(policy.snapshot, f"status_check_{policy.prefix}_restrict", False)
    for restrict in (True, False):
        with pytest.raises(HTTPException) as error:
            await policy.api.update_status_policy(
                _request(
                    policy, ["1001", "hidden-official", "official"], restrict=restrict
                ),
                None,
            )
        assert error.value.status_code == 503
    policy.service.set_settings.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_roster_keeps_bulk_edit_and_message_policy_validation(
    policy_api, monkeypatch
):
    policy = policy_api
    _roster(policy, monkeypatch, "ok")
    with pytest.raises(HTTPException) as error:
        await policy.api.update_status_policy(_request(policy, ["disabled"]), None)
    assert error.value.status_code == 400
    response = await policy.api.update_status_policy(
        _request(policy, [], restrict=False), None
    )
    assert response.restrict is False
    assert response.onebot_list_status == "ok"


@pytest.mark.asyncio
async def test_real_bridge_fetch_failure_keeps_official_edit_and_numeric_lock(
    policy_api, monkeypatch
):
    from admin.services import onebot_bridge

    policy = policy_api
    bot = MagicMock()
    bot.self_id = "42"
    bot.call_api = AsyncMock(side_effect=RuntimeError("roster unavailable"))
    monkeypatch.setattr(onebot_bridge, "get_bots", lambda: {"42": bot})
    monkeypatch.setattr(
        onebot_bridge,
        "list_sessions",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    openid="official",
                    kind="group" if policy.key == "group" else "c2c",
                    name="官方会话",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        policy.api,
        policy.roster_name,
        getattr(onebot_bridge, policy.roster_name),
    )
    onebot_bridge.invalidate_user_list_cache()
    response = await policy.api.get_status_policy(None)
    assert response.onebot_list_status == "incomplete"
    response = await policy.api.update_status_policy(
        _request(policy, ["1001", "hidden-official", "official"]), None
    )
    assert response.restrict is True
    assert getattr(response, f"enabled_{policy.key}_ids") == [
        "1001",
        "hidden-official",
        "official",
    ]
    with pytest.raises(HTTPException) as error:
        await policy.api.update_status_policy(
            _request(policy, ["hidden-official", "official"]), None
        )
    assert error.value.status_code == 503
    assert bot.call_api.await_count > 0
