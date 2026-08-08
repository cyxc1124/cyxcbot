"""Shared media directory for protocol-side file:// video send."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Linux / Docker：写在 QQ 数据目录下的 tmp，避免弄脏协议端根目录；卷仍挂 /root/.config/QQ。
_LINUX_DEFAULT = Path("/root/.config/QQ") / "tmp"
# Windows / macOS 等：落在机器草工作目录下的 data/tmp（Compose/Helm 已持久化 /app/data）。
# Linux 普通用户本机启动时 /root 不可写，也回落到此路径。
_LOCAL_DEFAULT = Path("data") / "tmp"


def _linux_qq_tmp_usable() -> bool:
    """Docker/K8s（常 root + 挂载）可用；本机非 root 一般不可写。"""
    target = _LINUX_DEFAULT
    try:
        if target.exists():
            return target.is_dir() and os.access(target, os.W_OK)
        parent = target.parent  # /root/.config/QQ
        if parent.is_dir():
            return os.access(parent, os.W_OK)
        return os.access(Path("/root"), os.W_OK)
    except OSError:
        return False


def default_shared_media_dir() -> Path:
    if sys.platform.startswith("linux") and _linux_qq_tmp_usable():
        return _LINUX_DEFAULT
    return _LOCAL_DEFAULT


def resolve_shared_media_dir(configured: str | None) -> Path:
    """空配置走平台默认；非空则 expanduser，相对路径相对进程 cwd。"""
    raw = (configured or "").strip()
    if not raw:
        return default_shared_media_dir()
    return Path(raw).expanduser()
