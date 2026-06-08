"""OneBot group list endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from admin.deps import CurrentUser, RequireSetup
from admin.schemas.groups import GroupInfo, GroupListResponse
from admin.services.onebot_bridge import get_group_list

router = APIRouter(
    prefix="/groups",
    tags=["groups"],
    dependencies=[RequireSetup],
)


@router.get("", response_model=GroupListResponse)
async def list_groups(_: CurrentUser):
    groups = await get_group_list()
    return GroupListResponse(groups=[GroupInfo(**g) for g in groups])
