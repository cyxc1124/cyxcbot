"""Shared media directory for protocol-side file:// video send."""

from __future__ import annotations

from pathlib import Path

# 通用默认：机器草工作目录下（Compose/Helm 已持久化 /app/data）。
# 与 LLBot 等协议端共享 QQ 数据目录时，请在 Web Admin 显式配置
# （常见为 /root/.config/QQ/tmp，卷仍挂 QQ 数据根）。
_DEFAULT = Path("data") / "tmp"


def default_shared_media_dir() -> Path:
    return _DEFAULT


def resolve_shared_media_dir(configured: str | None) -> Path:
    """空配置走默认 data/tmp；非空则 expanduser，相对路径相对进程 cwd。"""
    raw = (configured or "").strip()
    if not raw:
        return default_shared_media_dir()
    return Path(raw).expanduser()
