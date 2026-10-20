"""Password changes through the real auth routes and an isolated database."""

from __future__ import annotations

import importlib
import sys

import bcrypt
import nonebot
import pytest
from fastapi import FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.db_test_helpers import ensure_real_db_modules

OLD_PASSWORD = "old-password123"
NEW_PASSWORD = "new-password456"


@pytest.fixture
async def auth_client(tmp_path, monkeypatch, request):
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(
            sqlalchemy_database_url="sqlite+aiosqlite:///:memory:",
            alembic_startup_check=False,
        )
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")
    importlib.import_module("shared.db.models")
    ensure_real_db_modules()
    from admin import deps
    from admin.api.v1 import auth, setup
    from shared.db.base import Model

    importlib.reload(deps)
    importlib.reload(auth)
    importlib.reload(setup)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    for module in (deps, auth, setup):
        monkeypatch.setattr(module, "get_session", factory)
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(setup.router, prefix="/api/v1")
    try:
        async with AsyncClient(
            transport=ASGITransport(app), base_url="http://test/api/v1/"
        ) as client:
            if getattr(request, "param", None) != "uninitialized":
                response = await client.post(
                    "setup", json={"username": "admin", "password": OLD_PASSWORD}
                )
                assert response.status_code == 200
                client.headers["Authorization"] = (
                    f"Bearer {response.json()['access_token']}"
                )
            yield client, factory
    finally:
        await engine.dispose()


async def test_password_change_rotates_tokens_and_preserves_other_accounts(auth_client):
    from admin.auth.password import hash_password, verify_password
    from shared.db.models import User

    client, factory = auth_client
    old_authorization = client.headers["Authorization"]
    assert (await client.get("auth/me")).status_code == 200
    other_hash = hash_password("other-password")
    async with factory.begin() as session:
        session.add(User(username="other", password_hash=other_hash, is_admin=False))

    response = await client.put(
        "auth/password",
        json={"current_password": OLD_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 200
    new_token = response.json()["access_token"]
    assert (await client.get("auth/me")).status_code == 401
    client.headers["Authorization"] = f"Bearer {new_token}"
    assert (await client.get("auth/me")).status_code == 200
    assert client.headers["Authorization"] != old_authorization
    for password, expected in [(OLD_PASSWORD, 401), (NEW_PASSWORD, 200)]:
        login = await client.post(
            "auth/login", json={"username": "admin", "password": password}
        )
        assert login.status_code == expected
        if expected == 200:
            assert (
                await client.get(
                    "auth/me",
                    headers={"Authorization": f"Bearer {login.json()['access_token']}"},
                )
            ).status_code == 200
    async with factory() as session:
        admin = await session.scalar(select(User).where(User.username == "admin"))
        other = await session.scalar(select(User).where(User.username == "other"))
        assert admin.password_hash != NEW_PASSWORD
        assert verify_password(NEW_PASSWORD, admin.password_hash)
        assert other.password_hash == other_hash


@pytest.mark.parametrize(
    ("current", "new", "expected"),
    [
        ("wrong-password", NEW_PASSWORD, 400),
        (OLD_PASSWORD, OLD_PASSWORD, 400),
        (OLD_PASSWORD, "short", 422),
        (OLD_PASSWORD, "中" * 25, 422),
        (OLD_PASSWORD, "a" * 73, 422),
    ],
)
async def test_rejected_changes_preserve_password_and_session(
    auth_client, current, new, expected
):
    client, _ = auth_client
    response = await client.put(
        "auth/password", json={"current_password": current, "new_password": new}
    )
    assert response.status_code == expected
    assert (await client.get("auth/me")).status_code == 200
    assert (
        await client.post(
            "auth/login", json={"username": "admin", "password": OLD_PASSWORD}
        )
    ).status_code == 200


async def test_password_change_requires_authenticated_user(auth_client):
    client, _ = auth_client
    client.headers.pop("Authorization")
    response = await client.put(
        "auth/password",
        json={"current_password": OLD_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 401


async def test_token_without_password_fingerprint_requires_login(auth_client):
    from admin.auth.jwt import decode_access_token
    from admin.config import get_jwt_algorithm, get_jwt_secret

    client, _ = auth_client
    payload = decode_access_token(
        client.headers["Authorization"].removeprefix("Bearer ")
    )
    del payload["pwd"]
    legacy = jwt.encode(payload, get_jwt_secret(), algorithm=get_jwt_algorithm())
    response = await client.get(
        "auth/me", headers={"Authorization": f"Bearer {legacy}"}
    )
    assert response.status_code == 401


async def test_legacy_current_password_and_multibyte_new_password(auth_client):
    from shared.db.models import User

    client, factory = auth_client
    legacy_password = "中" * 25
    async with factory.begin() as session:
        user = await session.scalar(select(User).where(User.username == "admin"))
        user.password_hash = bcrypt.hashpw(
            legacy_password.encode("utf-8")[:72], bcrypt.gensalt()
        ).decode()
    login = await client.post(
        "auth/login", json={"username": "admin", "password": legacy_password}
    )
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    response = await client.put(
        "auth/password",
        json={"current_password": legacy_password, "new_password": "新" * 24},
    )
    assert response.status_code == 200


async def test_non_admin_can_change_own_password(auth_client):
    from admin.auth.password import hash_password
    from shared.db.models import User

    client, factory = auth_client
    async with factory.begin() as session:
        session.add(
            User(
                username="regular",
                password_hash=hash_password(OLD_PASSWORD),
                is_admin=False,
            )
        )
    login = await client.post(
        "auth/login", json={"username": "regular", "password": OLD_PASSWORD}
    )
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    response = await client.put(
        "auth/password",
        json={"current_password": OLD_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 200
    assert (
        await client.post(
            "auth/login", json={"username": "admin", "password": OLD_PASSWORD}
        )
    ).status_code == 200


async def test_concurrent_change_cannot_overwrite_a_new_password(auth_client):
    from admin.api.v1.auth import change_password
    from admin.auth.password import verify_password
    from admin.schemas.common import ChangePasswordRequest
    from shared.db.models import User

    _, factory = auth_client
    request = Request(
        {
            "type": "http",
            "method": "PUT",
            "scheme": "http",
            "server": ("test", 80),
            "path": "/api/v1/auth/password",
            "headers": [],
        }
    )
    async with factory() as session:
        user = await session.scalar(select(User).where(User.username == "admin"))
        session.expunge(user)
    await change_password(
        ChangePasswordRequest(current_password=OLD_PASSWORD, new_password=NEW_PASSWORD),
        user,
        request,
    )
    with pytest.raises(HTTPException) as exc:
        await change_password(
            ChangePasswordRequest(
                current_password=OLD_PASSWORD, new_password="racing-password"
            ),
            user,
            request,
        )
    assert exc.value.status_code == 409
    async with factory() as session:
        user = await session.scalar(select(User).where(User.username == "admin"))
        assert verify_password(NEW_PASSWORD, user.password_hash)


BROWSER_HEADERS = {"X-Cyxcbot-Session": "cookie"}


async def browser_login(client, headers=None):
    client.headers.pop("Authorization", None)
    response = await client.post(
        "auth/login",
        headers=headers or BROWSER_HEADERS,
        json={"username": "admin", "password": OLD_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Authenticated"}
    assert response.headers["cache-control"] == "no-store"
    return response


async def test_cookie_login_reload_password_rotation_and_logout(auth_client):
    client, _ = auth_client
    response = await browser_login(client)
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api/v1" in cookie
    assert "Domain=" not in cookie
    assert "Secure" not in cookie
    old_token = response.cookies["cyxcbot_session"]
    # A reloaded SPA has no token or Authorization header to restore.
    assert (await client.get("auth/me", headers=BROWSER_HEADERS)).status_code == 200
    assert (await client.get("auth/me")).status_code == 403
    changed = await client.put(
        "auth/password",
        headers=BROWSER_HEADERS,
        json={"current_password": OLD_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 200
    assert changed.json() == {"message": "Authenticated"}
    assert changed.cookies["cyxcbot_session"] != old_token
    assert (await client.get("auth/me", headers=BROWSER_HEADERS)).status_code == 200
    expired = await client.get(
        "auth/me", headers={"Authorization": f"Bearer {old_token}"}
    )
    assert expired.status_code == 401
    assert "set-cookie" not in expired.headers
    logout = await client.post("auth/logout", headers=BROWSER_HEADERS)
    assert logout.status_code == 200
    assert "Max-Age=0" in logout.headers["set-cookie"]
    assert (await client.get("auth/me", headers=BROWSER_HEADERS)).status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        {**BROWSER_HEADERS, "Sec-Fetch-Site": "cross-site"},
        {**BROWSER_HEADERS, "Sec-Fetch-Site": "same-site"},
        {**BROWSER_HEADERS, "Sec-Fetch-Site": "invalid"},
        {**BROWSER_HEADERS, "Sec-Fetch-Site": ""},
        {**BROWSER_HEADERS, "Origin": "http://test.evil"},
        {**BROWSER_HEADERS, "Origin": "http://test:81"},
        {**BROWSER_HEADERS, "Origin": "https://test"},
        {**BROWSER_HEADERS, "Origin": "null"},
        {"X-Cyxcbot-Session": "invalid"},
    ],
)
async def test_cross_origin_cookie_requests_cannot_use_or_replace_session(
    auth_client, headers
):
    client, _ = auth_client
    await browser_login(client)
    token = client.cookies["cyxcbot_session"]
    for method, path, body in [
        ("GET", "auth/me", None),
        ("POST", "auth/login", {"username": "admin", "password": OLD_PASSWORD}),
        ("POST", "auth/logout", None),
        (
            "PUT",
            "auth/password",
            {"current_password": OLD_PASSWORD, "new_password": NEW_PASSWORD},
        ),
        ("POST", "setup", {"username": "other", "password": OLD_PASSWORD}),
    ]:
        response = await client.request(method, path, headers=headers, json=body)
        assert response.status_code == 403
        assert "set-cookie" not in response.headers
    assert client.cookies["cyxcbot_session"] == token
    assert (await client.get("auth/me", headers=BROWSER_HEADERS)).status_code == 200


@pytest.mark.parametrize(
    "authorization", ["Bearer invalid", "Basic invalid", "Bearer "]
)
async def test_invalid_explicit_bearer_does_not_fall_back_to_valid_cookie(
    auth_client, authorization
):
    client, _ = auth_client
    await browser_login(client)
    response = await client.get(
        "auth/me", headers={**BROWSER_HEADERS, "Authorization": authorization}
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "base_url,headers,secure",
    [
        ("http://test/api/v1/", {**BROWSER_HEADERS, "Origin": "http://test"}, False),
        ("https://test/api/v1/", {**BROWSER_HEADERS, "Origin": "https://test"}, True),
        (
            "http://upstream/api/v1/",
            {
                **BROWSER_HEADERS,
                "Origin": "https://bot.example",
                "Sec-Fetch-Site": "same-origin",
            },
            True,
        ),
    ],
)
async def test_cookie_secure_flag_follows_direct_or_browser_https(
    auth_client, base_url, headers, secure
):
    client, _ = auth_client
    client.base_url = base_url
    response = await browser_login(client, headers)
    assert ("Secure" in response.headers["set-cookie"]) is secure


@pytest.mark.parametrize("auth_client", ["uninitialized"], indirect=True)
async def test_browser_setup_returns_only_http_only_cookie(auth_client):
    client, _ = auth_client
    rejected = await client.post(
        "setup",
        headers={**BROWSER_HEADERS, "Sec-Fetch-Site": "cross-site"},
        json={"username": "hostile", "password": OLD_PASSWORD},
    )
    assert rejected.status_code == 403
    assert (await client.get("setup/status")).json()["initialized"] is False
    response = await client.post(
        "setup",
        headers=BROWSER_HEADERS,
        json={"username": "first-admin", "password": OLD_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Authenticated"}
    assert "HttpOnly" in response.headers["set-cookie"]
    assert (await client.get("auth/me", headers=BROWSER_HEADERS)).json()[
        "username"
    ] == "first-admin"


async def test_bad_cookie_is_rejected_and_can_still_be_logged_out(auth_client):
    client, _ = auth_client
    client.headers.pop("Authorization")
    client.cookies.set("cyxcbot_session", "invalid", path="/api/v1")
    response = await client.get("auth/me", headers=BROWSER_HEADERS)
    assert response.status_code == 401
    assert "set-cookie" not in response.headers
    assert (
        await client.post("auth/logout", headers=BROWSER_HEADERS)
    ).status_code == 200


async def test_browser_cookie_cors_disallows_credentialed_preflights(auth_client):
    from admin.app import create_app

    async with AsyncClient(
        transport=ASGITransport(create_app()), base_url="http://test"
    ) as client:
        response = await client.options(
            "/api/v1/auth/password",
            headers={
                "Origin": "http://hostile.test",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "Content-Type,X-Cyxcbot-Session",
            },
        )
    assert response.status_code == 200
    assert "access-control-allow-credentials" not in response.headers
