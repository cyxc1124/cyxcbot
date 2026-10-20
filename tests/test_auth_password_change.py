"""Password changes through the real auth routes and an isolated database."""

from __future__ import annotations

import importlib
import sys

import bcrypt
import nonebot
import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.db_test_helpers import ensure_real_db_modules

OLD_PASSWORD = "old-password123"
NEW_PASSWORD = "new-password456"


@pytest.fixture
async def auth_client(tmp_path, monkeypatch):
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
    async with factory() as session:
        user = await session.scalar(select(User).where(User.username == "admin"))
        session.expunge(user)
    await change_password(
        ChangePasswordRequest(current_password=OLD_PASSWORD, new_password=NEW_PASSWORD),
        user,
    )
    with pytest.raises(HTTPException) as exc:
        await change_password(
            ChangePasswordRequest(
                current_password=OLD_PASSWORD, new_password="racing-password"
            ),
            user,
        )
    assert exc.value.status_code == 409
    async with factory() as session:
        user = await session.scalar(select(User).where(User.username == "admin"))
        assert verify_password(NEW_PASSWORD, user.password_hash)
