"""About / version info endpoints."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import time
from pathlib import Path
from urllib.request import Request, urlopen

from fastapi import APIRouter

from admin.deps import AdminUser, RequireSetup
from admin.schemas.about import AboutResponse

router = APIRouter(
    tags=["about"],
    dependencies=[RequireSetup],
)

# ponytail: module-level cache for GitHub update check (avoid per-request API calls)
_update_cache: dict[str, object] = {"available": None, "url": None, "ts": 0.0}
_CACHE_TTL = 1800  # 30 minutes
_GITHUB_REPO = "cyxc1124/cyxcbot"


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


def _fastapi_version() -> str | None:
    try:
        import fastapi

        return fastapi.__version__
    except Exception:
        return None


def _frontend_versions() -> tuple[str | None, str | None]:
    """ponytail: reads web/package.json at startup.
    Returns (react_version, tailwindcss_version)."""
    try:
        pkg_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "web"
            / "package.json"
        )
        with open(pkg_path) as f:
            pkg = json.load(f)
        react = pkg.get("dependencies", {}).get("react", "").lstrip("^")
        tailwind = pkg.get("devDependencies", {}).get("tailwindcss", "").lstrip("^")
        return (react or None, tailwind or None)
    except Exception:
        return (None, None)


def _fetch_json(url: str) -> dict | None:
    """ponytail: sync HTTP with 5s timeout; single-repo, no session reuse needed."""
    try:
        req = Request(
            url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "cyxcbot"},
        )
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _check_github_update(
    git_tag: str | None, git_commit: str | None, git_branch: str | None
) -> tuple[bool | None, str | None]:
    """Returns (update_available, update_url)."""
    if git_tag:
        data = _fetch_json(f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest")
        if data and data.get("tag_name") != git_tag:
            return (True, data.get("html_url"))
        if data:
            return (False, None)
    elif git_branch and git_commit:
        data = _fetch_json(f"https://api.github.com/repos/{_GITHUB_REPO}/commits/{git_branch}")
        if data:
            latest = data.get("sha", "")
            if latest[:8] != git_commit[:8]:
                return (True, data.get("html_url"))
            return (False, None)
    return (None, None)


async def _refresh_update_cache(
    git_tag: str | None, git_commit: str | None, git_branch: str | None,
) -> None:
    """Offloads sync GitHub HTTP to thread pool."""
    try:
        available, url = await asyncio.to_thread(
            _check_github_update, git_tag, git_commit, git_branch,
        )
        _update_cache["available"] = available
        _update_cache["url"] = url
        _update_cache["ts"] = time.time()
    except Exception:
        pass


@router.get("/about", response_model=AboutResponse)
async def get_about(_: AdminUser):
    nonebot_version = _nonebot_version()
    fastapi_version = _fastapi_version()
    react_version, tailwindcss_version = _frontend_versions()

    framework = "FastAPI + NoneBot2"
    if fastapi_version and nonebot_version:
        framework = f"FastAPI {fastapi_version} + NoneBot2 {nonebot_version}"
    elif nonebot_version:
        framework = f"FastAPI + NoneBot2 {nonebot_version}"
    elif fastapi_version:
        framework = f"FastAPI {fastapi_version} + NoneBot2"

    git_tag = _env("GIT_TAG")
    git_commit = _short_commit(_env("GIT_COMMIT"))
    git_branch = _env("GIT_BRANCH")

    # Fire-and-forget async refresh if stale
    cached = _update_cache["available"]
    if cached is None or time.time() - _update_cache["ts"] > _CACHE_TTL:
        asyncio.create_task(_refresh_update_cache(git_tag, git_commit, git_branch))

    return AboutResponse(
        app_name="机器草",
        web_frontend="React + Tailwind CSS",
        backend_framework=framework,
        build_version=_build_version(),
        git_branch=git_branch,
        git_tag=git_tag,
        git_commit=git_commit,
        build_time=_env("BUILD_TIME"),
        build_number=_env("BUILD_NUMBER"),
        python_version=platform.python_version(),
        fastapi_version=fastapi_version,
        react_version=react_version,
        tailwindcss_version=tailwindcss_version,
        update_available=cached if isinstance(cached, bool) else None,
        update_url=str(_update_cache["url"]) if _update_cache["url"] else None,
    )
