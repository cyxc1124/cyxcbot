"""Shared media directory defaults for file:// video send."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from shared.config.shared_media import (
    default_shared_media_dir,
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
