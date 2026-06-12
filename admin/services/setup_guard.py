"""One-time setup guard backed by a database singleton constraint."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from shared.db.models import SETUP_COMPLETED_KEY, SystemSetting, User


async def claim_initial_setup(session) -> None:
    """Reject completed setups and atomically reserve initialization in this transaction."""
    count = await session.scalar(select(func.count()).select_from(User)) or 0
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Setup already completed",
        )

    try:
        session.add(SystemSetting(key=SETUP_COMPLETED_KEY, value="1"))
        await session.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Setup already completed",
        ) from None
