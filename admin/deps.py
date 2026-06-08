"""FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select

from nonebot_plugin_orm import get_session

from admin.auth.jwt import decode_access_token
from shared.db.models import User

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    username = str(payload["sub"])
    session = get_session()
    async with session.begin():
        user = await session.scalar(select(User).where(User.username == username))
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        # Detach scalars before session closes
        await session.refresh(user)
        session.expunge(user)
    request.state.user = user
    return user


async def require_setup_complete() -> None:
    session = get_session()
    async with session.begin():
        count = await session.scalar(select(func.count()).select_from(User))
    if not count:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Setup required")


CurrentUser = Annotated[User, Depends(get_current_user)]
RequireSetup = Depends(require_setup_complete)
