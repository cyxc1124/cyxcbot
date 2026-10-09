"""Message-policy handlers with cached official sessions and partial OneBot rosters."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from admin.schemas.groups import (
    GroupInfo,
    GroupMessagePolicyResponse,
    GroupMessagePolicyUpdateRequest,
)
from admin.schemas.private import (
    FriendInfo,
    PrivateMessagePolicyResponse,
    PrivateMessagePolicyUpdateRequest,
)
from admin.services.message_policy import (
    ensure_message_policy_edit_allowed,
    visible_message_policy_rows,
)
from shared.group_policy import is_group_message_enabled_from_snapshot
from shared.private_policy import is_private_message_enabled_from_snapshot


def load_handlers(scope, snapshot, rows, fetch_status):
    module_name, key, prefix = (
        ("groups", "group", "message_group")
        if scope == "group"
        else ("private", "user", "message_private")
    )
    source = Path(__file__).resolve().parents[1] / "admin/api/v1" / f"{module_name}.py"
    policy_ids = f"message_enabled_{key}_ids"
    service = SimpleNamespace(get_snapshot=lambda: snapshot)

    async def set_settings(updates):
        setattr(snapshot, f"{prefix}_restrict", updates[f"{prefix}_restrict"] == "true")
        setattr(snapshot, policy_ids, json.loads(updates[policy_ids]))

    service.set_settings = AsyncMock(side_effect=set_settings)
    service.reload = AsyncMock()
    fetch = AsyncMock(return_value=(rows, fetch_status))
    namespace = {
        "get_config_service": lambda: service,
        "get_group_list_with_status": fetch,
        "get_friend_list_with_availability": fetch,
        "invalidate_user_list_cache": lambda: None,
        "_group_list_available": lambda status: status == "ok",
        "_friend_list_available": lambda status: status == "ok",
        "visible_message_policy_rows": visible_message_policy_rows,
        "ensure_message_policy_edit_allowed": ensure_message_policy_edit_allowed,
        "GroupInfo": GroupInfo,
        "FriendInfo": FriendInfo,
        "GroupMessagePolicyResponse": GroupMessagePolicyResponse,
        "PrivateMessagePolicyResponse": PrivateMessagePolicyResponse,
        "json": json,
    }
    functions = [
        node
        for node in ast.parse(source.read_text()).body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name in {"get_message_policy", "update_message_policy"}
    ]
    for node in functions:
        node.decorator_list = []
    future = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0
    )
    code = ast.fix_missing_locations(
        ast.Module(body=[future, *functions], type_ignores=[])
    )
    exec(compile(code, str(source), "exec"), namespace)
    return namespace, service


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "private"])
@pytest.mark.parametrize("fetch_status", ["ok", "offline", "incomplete"])
async def test_cached_official_session_can_enable_disable_and_reload(
    scope, fetch_status
):
    key = "group" if scope == "group" else "user"
    snapshot = SimpleNamespace(
        message_group_restrict=True,
        message_private_restrict=True,
        message_enabled_group_ids=["1001", "hidden-official"],
        message_enabled_user_ids=["1001", "hidden-official"],
    )
    rows = [
        {f"{key}_id": "official", "source": "official"},
        {f"{key}_id": "1002", "source": "onebot"},
    ]
    handlers, service = load_handlers(scope, snapshot, rows, fetch_status)
    policy = await handlers["get_message_policy"](None)
    assert policy.onebot_list_status == fetch_status
    returned = policy.groups if scope == "group" else policy.users
    assert [getattr(row, f"{key}_id") for row in returned] == (
        ["official"] if fetch_status == "offline" else ["official", "1002"]
    )
    request = (
        GroupMessagePolicyUpdateRequest
        if scope == "group"
        else PrivateMessagePolicyUpdateRequest
    )
    guard = (
        is_group_message_enabled_from_snapshot
        if scope == "group"
        else is_private_message_enabled_from_snapshot
    )
    assert not guard("official", snapshot)
    for enabled in (True, False):
        expected = ["1001", "hidden-official"] + (["official"] if enabled else [])
        response = await handlers["update_message_policy"](
            request(restrict=True, **{f"enabled_{key}_ids": expected}), None
        )
        assert response.onebot_list_status == fetch_status
        assert getattr(response, f"enabled_{key}_ids") == expected
        assert guard("official", snapshot) is enabled
        assert guard("1001", snapshot)
        assert not guard("unknown-official", snapshot)
        reloaded = await handlers["get_message_policy"](None)
        assert reloaded.onebot_list_status == fetch_status
        assert getattr(reloaded, f"enabled_{key}_ids") == expected
    assert service.set_settings.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "private"])
@pytest.mark.parametrize("change", ["global", "numeric", "hidden", "unknown"])
async def test_partial_roster_rejects_changes_outside_known_official_sessions(
    scope, change
):
    key = "group" if scope == "group" else "user"
    snapshot = SimpleNamespace(
        message_group_restrict=True,
        message_private_restrict=True,
        message_enabled_group_ids=["1001"],
        message_enabled_user_ids=["1001"],
    )
    rows = [
        {f"{key}_id": "official", "source": "official"},
        {f"{key}_id": "1002", "source": "onebot"},
    ]
    handlers, service = load_handlers(scope, snapshot, rows, "incomplete")
    enabled_ids = (
        []
        if change in {"global", "hidden"}
        else ["1001", "1002" if change == "numeric" else "unknown"]
    )
    request = (
        GroupMessagePolicyUpdateRequest
        if scope == "group"
        else PrivateMessagePolicyUpdateRequest
    )
    with pytest.raises(HTTPException) as error:
        await handlers["update_message_policy"](
            request(restrict=change != "global", **{f"enabled_{key}_ids": enabled_ids}),
            None,
        )
    assert error.value.status_code == 503
    service.set_settings.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "private"])
@pytest.mark.parametrize("fetch_status", ["offline", "incomplete"])
async def test_unrestricted_partial_roster_is_read_only(scope, fetch_status):
    key = "group" if scope == "group" else "user"
    snapshot = SimpleNamespace(
        message_group_restrict=False,
        message_private_restrict=False,
        message_enabled_group_ids=["1001"],
        message_enabled_user_ids=["1001"],
    )
    rows = [{f"{key}_id": "official", "source": "official"}]
    handlers, service = load_handlers(scope, snapshot, rows, fetch_status)
    request = (
        GroupMessagePolicyUpdateRequest
        if scope == "group"
        else PrivateMessagePolicyUpdateRequest
    )
    with pytest.raises(HTTPException) as error:
        await handlers["update_message_policy"](
            request(restrict=False, **{f"enabled_{key}_ids": ["1001", "official"]}),
            None,
        )
    assert error.value.status_code == 503
    service.set_settings.assert_not_awaited()


def test_complete_roster_keeps_global_policy_edit_support():
    ensure_message_policy_edit_allowed(
        fetch_status="ok",
        rows=[],
        id_key="user_id",
        current_restrict=True,
        current_ids=["1001"],
        restrict=False,
        enabled_ids=[],
    )
