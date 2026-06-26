"""Tests for admin SPA static path containment."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from admin.spa_path import path_under_base


def test_path_under_base_allows_file_in_base(tmp_path: Path) -> None:
    (tmp_path / "ok.txt").write_text("x")
    assert path_under_base(tmp_path, "ok.txt").name == "ok.txt"


def test_path_under_base_blocks_traversal(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    with pytest.raises(HTTPException) as exc:
        path_under_base(tmp_path / "nested", "../outside")
    assert exc.value.status_code == 404


def test_path_under_base_blocks_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        path_under_base(tmp_path, "/etc/passwd")
    assert exc.value.status_code == 404
