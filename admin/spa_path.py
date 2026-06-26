"""Safe path resolution for SPA static file serving."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse


def _realpath_under_base(base: Path, rel: str) -> str:
    """Return real path for rel under base; 404 if escaped (includes symlink targets)."""
    root = os.path.realpath(str(base))
    target = os.path.realpath(os.path.join(root, rel))
    if target != root and not target.startswith(root + os.sep):
        raise HTTPException(status_code=404, detail="Not found")
    return target


def static_file_response(base: Path, rel: str) -> FileResponse | None:
    """Return FileResponse when rel resolves to a file under base."""
    target = _realpath_under_base(base, rel)
    if os.path.isfile(target):
        return FileResponse(target)
    return None


def index_file_response(base: Path) -> FileResponse | None:
    """Return FileResponse for index.html under base when present."""
    target = _realpath_under_base(base, "index.html")
    if os.path.isfile(target):
        return FileResponse(target)
    return None
