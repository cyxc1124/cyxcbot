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


def _env(key: str) -> str | None:
    value = os.getenv(key, "").strip()
    return value or None


def _short_commit(commit: str | None) -> str | None:
    if not commit:
        return None
    return commit[:8] if len(commit) > 8 else commit


def _build_version() -> str:
    tag = _env("GIT_TAG")
    if tag:
        return tag
    branch = _env("GIT_BRANCH")
    commit = _short_commit(_env("GIT_COMMIT"))
    if branch and commit:
        return f"{branch}@{commit}"
    if branch:
        return branch
    if commit:
        return commit
    build_version = _env("BUILD_VERSION")
    if build_version:
        return build_version
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
        git_branch=_env("GIT_BRANCH"),
        git_tag=_env("GIT_TAG"),
        git_commit=_short_commit(_env("GIT_COMMIT")),
        build_time=_env("BUILD_TIME"),
        build_number=_env("BUILD_NUMBER"),
        python_version=platform.python_version(),
    )
