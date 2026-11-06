"""Multi-account persistence, login boundaries and shared request rotation."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from test_config_service_load_perf import db_context as db_context

from shared.bilibili.accounts import (
    BilibiliAccount,
    BilibiliAccountPool,
    bilibili_account_pool,
    encrypt_accounts,
    load_accounts,
)
from shared.security.crypto import decrypt_value, encrypt_value

ACCOUNTS = (
    BilibiliAccount("100", "SESSDATA=first; DedeUserID=100", "账号一"),
    BilibiliAccount("200", "SESSDATA=second; DedeUserID=200", "账号二"),
)


@pytest.fixture
async def service(db_context, monkeypatch):
    _, factory, ConfigService, *_ = db_context
    monkeypatch.setattr("shared.config.service.get_session", factory)
    return ConfigService()


def test_legacy_and_encrypted_round_trip():
    legacy = encrypt_value(ACCOUNTS[0].cookie)
    assert load_accounts("", legacy) == (BilibiliAccount("100", ACCOUNTS[0].cookie),)
    encrypted = encrypt_accounts(ACCOUNTS)
    assert "SESSDATA" not in encrypted and "账号一" not in encrypted
    assert "SESSDATA" not in repr(ACCOUNTS)
    assert load_accounts(encrypted, legacy) == ACCOUNTS
    assert load_accounts(encrypt_accounts(()), legacy) == ()
    assert load_accounts("", encrypt_value("SESSDATA=old"))[0].uid == "legacy"


@pytest.mark.parametrize("data", [{}, [{"uid": "100"}], [{"uid": "100", "cookie": 3}]])
def test_invalid_stored_accounts_are_rejected(data):
    with pytest.raises(ValueError):
        load_accounts(encrypt_value(json.dumps(data)))


async def test_legacy_add_relogin_remove_and_restart(service):
    await service.set_settings(
        {"bilibili_cookie_encrypted": encrypt_value(ACCOUNTS[0].cookie)}
    )
    snapshot = await service.load()
    assert snapshot.bilibili_accounts[0].uid == "100"
    await service.upsert_bilibili_account(ACCOUNTS[1])
    renewed = BilibiliAccount("100", "SESSDATA=renewed; DedeUserID=100", "新名字")
    await service.upsert_bilibili_account(renewed)
    assert service.get_snapshot().bilibili_accounts == (renewed, ACCOUNTS[1])
    assert service.get_snapshot().bilibili_cookie == renewed.cookie
    assert (
        decrypt_value(await service.get_setting("bilibili_cookie_encrypted"))
        == renewed.cookie
    )
    assert await type(service)().load() == service.get_snapshot()
    await service.remove_bilibili_account("100")
    assert service.get_snapshot().bilibili_accounts == (ACCOUNTS[1],)
    assert bilibili_account_pool.select_cookie() == ACCOUNTS[1].cookie
    with pytest.raises(KeyError):
        await service.remove_bilibili_account("missing")
    await service.remove_bilibili_account("200")
    assert not (await type(service)().load()).bilibili_cookie_set
    assert await service.get_setting("bilibili_cookie_encrypted") == ""
    assert bilibili_account_pool.select_cookie(renewed.cookie) == ""


async def test_concurrent_adds_keep_both_accounts_and_logout_clears_all(service):
    await asyncio.gather(*(service.upsert_bilibili_account(row) for row in ACCOUNTS))
    assert service.get_snapshot().bilibili_accounts == ACCOUNTS
    await service.remove_bilibili_account()
    assert load_accounts(await service.get_setting("bilibili_accounts_encrypted")) == ()
    assert service.get_snapshot().bilibili_accounts == ()


async def test_corrupt_config_is_not_overwritten_by_login(service):
    await service.set_settings({"bilibili_accounts_encrypted": "corrupt"})
    with pytest.raises(ValueError):
        await service.upsert_bilibili_account(ACCOUNTS[0])
    assert await service.get_setting("bilibili_accounts_encrypted") == "corrupt"


async def test_process_wide_rotation_and_reload():
    pool = BilibiliAccountPool()
    assert pool.select_cookie("explicit") == "explicit"
    pool.configure(ACCOUNTS)

    async def select():
        await asyncio.sleep(0)
        return pool.select_cookie()

    assert (
        await asyncio.gather(*(select() for _ in range(20)))
        == [row.cookie for row in ACCOUNTS] * 10
    )
    pool.select_cookie()
    pool.configure(ACCOUNTS)
    assert pool.select_cookie() == ACCOUNTS[1].cookie
    pool.configure((ACCOUNTS[1],))
    assert pool.select_cookie() == ACCOUNTS[1].cookie
    pool.configure(())
    assert pool.select_cookie(ACCOUNTS[0].cookie) == ""


def response_session():
    response = MagicMock(status=200)
    response.json = AsyncMock(return_value={"code": 0, "data": {}})
    response.text = AsyncMock(return_value='{"code": 0, "data": {"items": []}}')
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.get.return_value = context
    return session, response


async def test_http_api_callers_share_rotation_and_keep_signing_cookie(monkeypatch):
    from utils.bilibili_api import wbi
    from utils.bilibili_api.dynamic_api import DynamicFetcher
    from utils.bilibili_api.live_api import LiveApi
    from utils.bilibili_api.video_api import VideoApi
    from utils.bilibili_api.video_download import fetch_playurl

    bilibili_account_pool.configure(ACCOUNTS)
    session, response = response_session()
    sign = AsyncMock(return_value="signed=1")
    monkeypatch.setattr(wbi, "sign_params", sign)
    dynamic = DynamicFetcher(session, "stale")
    video = VideoApi(session, "stale")
    live = LiveApi(session, "stale")
    await dynamic.fetch_user_dynamics("123")
    await live._get_info_by_room(123)
    await video.get_user_videos(123)
    await dynamic.fetch_dynamic_detail("123")
    await dynamic._get_user_name_from_api("456")
    await video.get_video_detail(bvid="BV123")
    response.json.return_value = {"code": 0, "data": {"dash": {}}}
    await fetch_playurl(session, bvid="BV123", cid=1, cookie="stale", qn=64)
    actual = [
        call.kwargs["headers"].get("Cookie") for call in session.get.call_args_list
    ]
    assert actual == [row.cookie for row in ACCOUNTS] * 3 + [ACCOUNTS[0].cookie]
    assert [call.args[2] for call in sign.call_args_list] == [ACCOUNTS[0].cookie] * 3


async def test_api_managers_do_not_reuse_server_cookies():
    from utils.bilibili_api.live_api import api_manager as live_manager
    from utils.bilibili_api.video_api import video_api_manager as video_manager

    for manager in (live_manager, video_manager):
        await manager.close()
        try:
            await manager.init(ACCOUNTS[0].cookie)
            assert isinstance(manager.api.session.cookie_jar, aiohttp.DummyCookieJar)
        finally:
            await manager.close()


async def test_account_api_checks_exact_cookie_and_never_returns_credentials(
    service, monkeypatch
):
    from admin.api.v1 import bilibili as api
    from admin.schemas.bilibili import QrcodePollRequest

    monkeypatch.setattr(api, "get_config_service", lambda: service)
    await service.upsert_bilibili_account(ACCOUNTS[0])
    poll = AsyncMock(
        return_value={
            "cookie_info": {"cookies": [{"name": "SESSDATA", "value": "second"}]}
        }
    )
    check = AsyncMock(
        return_value={
            "logged_in": True,
            "status": "logged_in",
            "configured": True,
            "uid": "200",
            "username": "账号二",
        }
    )
    monkeypatch.setattr(api, "poll_tv_qrcode_login", poll)
    monkeypatch.setattr(api, "check_bilibili_cookie", check)
    result = await api.poll_qrcode_login(QrcodePollRequest(qrcode={}), None)
    assert result.success and result.uid == "200"
    check.assert_awaited_once_with("SESSDATA=second")
    listed = await api.list_bilibili_accounts(None)
    assert [row.uid for row in listed] == ["100", "200"]
    assert "SESSDATA" not in " ".join(row.model_dump_json() for row in listed)
    await api.test_bilibili_account("100", None)
    check.assert_awaited_with(ACCOUNTS[0].cookie)
    check.return_value = {"logged_in": False, "status": "verify_failed"}
    result = await api.poll_qrcode_login(QrcodePollRequest(qrcode={}), None)
    assert not result.success
    assert len(service.get_snapshot().bilibili_accounts) == 2
    await api.remove_bilibili_account("100", None)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await api.test_bilibili_account("100", None)
    assert exc.value.status_code == 404
    await api.logout_bilibili(None)
    assert not service.get_snapshot().bilibili_cookie_set


async def test_aggregate_status_finds_healthy_secondary_account(service, monkeypatch):
    from admin.services import connection_status

    for row in ACCOUNTS:
        await service.upsert_bilibili_account(row)
    monkeypatch.setattr(connection_status, "get_config_service", lambda: service)
    check = AsyncMock(
        side_effect=[{"logged_in": False}, {"logged_in": True, "uid": "200"}]
    )
    monkeypatch.setattr(connection_status, "check_bilibili_cookie", check)
    assert (await connection_status.get_bilibili_connection_status())["uid"] == "200"
    assert [call.args[0] for call in check.call_args_list] == [
        row.cookie for row in ACCOUNTS
    ]
