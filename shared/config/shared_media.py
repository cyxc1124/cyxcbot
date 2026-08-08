"""Shared media directory for protocol-side file:// video send."""

from __future__ import annotations

import tempfile
from pathlib import Path

# 通用默认：机器草工作目录下（Compose/Helm 已持久化 /app/data）。
# 与 LLBot 等协议端共享 QQ 数据目录时，请在 Web Admin 显式配置
# （常见为 /root/.config/QQ/tmp，卷仍挂 QQ 数据根）。
_DEFAULT = Path("data") / "tmp"

# 跨 UID 协议端需目录可遍历（execute）；mkdtemp 默认 0700 会挡读。
_SHARED_DIR_MODE = 0o755
_SHARED_FILE_MODE = 0o644


def default_shared_media_dir() -> Path:
    return _DEFAULT


def resolve_shared_media_dir(configured: str | None) -> Path:
    """空配置走默认 data/tmp；非空则 expanduser，相对路径相对进程 cwd。"""
    raw = (configured or "").strip()
    if not raw:
        return default_shared_media_dir()
    return Path(raw).expanduser()


def _chmod_best_effort(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass


def ensure_shared_media_dir(configured: str | None) -> Path:
    """解析、创建共享根目录，并尽量设为协议端可遍历。"""
    path = resolve_shared_media_dir(configured)
    path.mkdir(parents=True, exist_ok=True)
    _chmod_best_effort(path, _SHARED_DIR_MODE)
    return path


def make_shared_workdir(media_dir: Path, *, prefix: str) -> Path:
    """在共享根下建临时子目录（纠正 mkdtemp 的 0700）。"""
    work = Path(tempfile.mkdtemp(prefix=prefix, dir=media_dir))
    _chmod_best_effort(work, _SHARED_DIR_MODE)
    return work


def chmod_shared_media_file(path: Path) -> None:
    """下载产物尽量对协议端 UID 可读。"""
    _chmod_best_effort(path, _SHARED_FILE_MODE)
