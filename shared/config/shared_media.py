"""Shared media directory for protocol-side file:// video send."""

from __future__ import annotations

import sys
from pathlib import Path

# Linux / Docker：写在 QQ 数据目录下的 tmp，避免弄脏协议端根目录；卷仍挂 /root/.config/QQ。
_LINUX_DEFAULT = Path("/root/.config/QQ") / "tmp"
# Windows / macOS 等：落在机器草工作目录下的 data/tmp（Compose/Helm 已持久化 /app/data）。
_LOCAL_DEFAULT = Path("data") / "tmp"


def default_shared_media_dir() -> Path:
    if sys.platform.startswith("linux"):
        return _LINUX_DEFAULT
    return _LOCAL_DEFAULT


def resolve_shared_media_dir(configured: str | None) -> Path:
    """空配置走平台默认；非空则 expanduser，相对路径相对进程 cwd。"""
    raw = (configured or "").strip()
    if not raw:
        return default_shared_media_dir()
    return Path(raw).expanduser()
