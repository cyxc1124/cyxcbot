"""About / version info endpoints."""

from __future__ import annotations

import os
import platform

from fastapi import APIRouter

from admin.deps import AdminUser, RequireSetup
from admin.schemas.about import AboutResponse

router = APIRouter(
    tags=["about"],
    dependencies=[RequireSetup],
)


def _build_version() -> str:
    for key in ("GIT_TAG", "GIT_COMMIT", "BUILD_VERSION"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return "dev"


def _nonebot_version() -> str | None:
    try:
        import nonebot

        return nonebot.__version__
    except Exception:
        return None


@router.get("/about", response_model=AboutResponse)
async def get_about(_: AdminUser):
    nonebot_version = _nonebot_version()
    framework = "FastAPI + NoneBot2"
    if nonebot_version:
        framework = f"FastAPI + NoneBot2 {nonebot_version}"

    return AboutResponse(
        app_name="机器草",
        web_frontend="React + Tailwind CSS",
        backend_framework=framework,
        build_version=_build_version(),
        python_version=platform.python_version(),
    )
