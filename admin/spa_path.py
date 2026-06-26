"""Safe path resolution for SPA static file serving."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException


def path_under_base(base: Path, rel: str) -> Path:
    """Resolve rel under base; 404 if escaped (includes symlink targets)."""
    root = os.path.realpath(str(base))
    target = os.path.realpath(os.path.join(root, rel))
    if target != root and not target.startswith(root + os.sep):
        raise HTTPException(status_code=404, detail="Not found")
    return Path(target)
