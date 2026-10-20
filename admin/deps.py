"""FastAPI dependencies."""

from __future__ import annotations

from hashlib import sha256
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from nonebot_plugin_orm import get_session
from sqlalchemy import func, select

from admin.auth.jwt import decode_access_token
from admin.auth.session import SESSION_COOKIE, require_browser_session
from shared.db.models import User

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
) -> User:
    if "Authorization" in request.headers:
        token = credentials.credentials if credentials else None
    else:
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            require_browser_session(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    username = str(payload["sub"])
    async with get_session() as session:
        async with session.begin():
            user = await session.scalar(select(User).where(User.username == username))
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
                )
            if (
                payload.get("pwd")
                != sha256(user.password_hash.encode("utf-8")).hexdigest()
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Password changed, please log in again",
                )
            # Detach scalars before session closes
            await session.refresh(user)
            session.expunge(user)
    request.state.user = user
    return user


async def get_admin_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin required"
        )
    return user


async def require_setup_complete() -> None:
    async with get_session() as session:
        async with session.begin():
            count = await session.scalar(select(func.count()).select_from(User))
    if not count:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Setup required"
        )


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]
RequireSetup = Depends(require_setup_complete)
