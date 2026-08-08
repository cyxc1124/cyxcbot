"""Shared media directory defaults for file:// video send."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from shared.config.shared_media import (
    chmod_shared_media_file,
    default_shared_media_dir,
    ensure_shared_media_dir,
    make_shared_workdir,
    resolve_shared_media_dir,
)


def test_default_is_data_tmp() -> None:
    assert default_shared_media_dir() == Path("data") / "tmp"


def test_resolve_empty_uses_default() -> None:
    assert resolve_shared_media_dir("") == Path("data") / "tmp"
    assert resolve_shared_media_dir("  ") == Path("data") / "tmp"
    assert resolve_shared_media_dir(None) == Path("data") / "tmp"


def test_resolve_custom_path() -> None:
    assert resolve_shared_media_dir("/root/.config/QQ/tmp") == Path(
        "/root/.config/QQ/tmp"
    )
    assert resolve_shared_media_dir("/mnt/nas/QQ") == Path("/mnt/nas/QQ")


def test_make_shared_workdir_is_traversable(tmp_path: Path) -> None:
    work = make_shared_workdir(tmp_path, prefix="douyin_")
    mode = stat.S_IMODE(work.stat().st_mode)
    assert mode == 0o755
    assert work.name.startswith("douyin_")
    # other users need execute bit to traverse
    assert mode & stat.S_IXOTH


def test_ensure_shared_media_dir_creates_traversable(tmp_path: Path) -> None:
    root = ensure_shared_media_dir(str(tmp_path / "media"))
    assert root.is_dir()
    assert stat.S_IMODE(root.stat().st_mode) == 0o755


def test_chmod_shared_media_file(tmp_path: Path) -> None:
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")
    os.chmod(f, 0o600)
    chmod_shared_media_file(f)
    assert stat.S_IMODE(f.stat().st_mode) == 0o644
