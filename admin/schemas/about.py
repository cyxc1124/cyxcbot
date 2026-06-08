"""About page API schemas."""

from __future__ import annotations

from pydantic import BaseModel


class AboutResponse(BaseModel):
    app_name: str
    web_frontend: str
    backend_framework: str
    build_version: str
    python_version: str
