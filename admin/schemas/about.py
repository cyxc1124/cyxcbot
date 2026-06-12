"""About page API schemas."""

from __future__ import annotations

from pydantic import BaseModel


class AboutResponse(BaseModel):
    app_name: str
    web_frontend: str
    backend_framework: str
    build_version: str
    git_branch: str | None = None
    git_tag: str | None = None
    git_commit: str | None = None
    build_time: str | None = None
    build_number: str | None = None
    python_version: str
