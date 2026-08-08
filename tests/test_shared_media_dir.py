"""Shared media directory defaults for file:// video send."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from shared.config.shared_media import (
    SharedMediaDirError,
    default_shared_media_dir,
    require_shared_media_dir,
    resolve_shared_media_dir,
)


def test_default_linux_path() -> None:
    with patch("shared.config.shared_media.sys.platform", "linux"):
        assert default_shared_media_dir() == Path("/root/.config/QQ") / "tmp"


def test_default_windows_and_macos_use_data_tmp() -> None:
    with patch("shared.config.shared_media.sys.platform", "win32"):
        assert default_shared_media_dir() == Path("data") / "tmp"
    with patch("shared.config.shared_media.sys.platform", "darwin"):
        assert default_shared_media_dir() == Path("data") / "tmp"


def test_resolve_empty_uses_platform_default() -> None:
    with patch("shared.config.shared_media.sys.platform", "linux"):
        assert resolve_shared_media_dir("") == Path("/root/.config/QQ") / "tmp"
        assert resolve_shared_media_dir("  ") == Path("/root/.config/QQ") / "tmp"
    with patch("shared.config.shared_media.sys.platform", "darwin"):
        assert resolve_shared_media_dir("") == Path("data") / "tmp"


def test_resolve_custom_path() -> None:
    assert resolve_shared_media_dir("/mnt/nas/QQ") == Path("/mnt/nas/QQ")


def test_require_shared_media_dir_ok(tmp_path: Path) -> None:
    assert require_shared_media_dir(str(tmp_path)) == tmp_path


def test_require_shared_media_dir_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(SharedMediaDirError, match="不存在"):
        require_shared_media_dir(str(missing))


def test_require_shared_media_dir_rejects_file(tmp_path: Path) -> None:
    file_path = tmp_path / "not-a-dir"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(SharedMediaDirError, match="不是目录"):
        require_shared_media_dir(str(file_path))
