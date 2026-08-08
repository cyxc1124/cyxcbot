"""Shared media directory defaults for file:// video send."""

from __future__ import annotations

from pathlib import Path

from shared.config.shared_media import (
    default_shared_media_dir,
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
