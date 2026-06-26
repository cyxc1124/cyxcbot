"""Tests for admin SPA static path containment."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from admin.spa_path import static_file_response


def test_static_file_response_allows_file_in_base(tmp_path: Path) -> None:
    (tmp_path / "ok.txt").write_text("x")
    response = static_file_response(tmp_path, "ok.txt")
    assert response is not None
    assert response.path == str((tmp_path / "ok.txt").resolve())


def test_static_file_response_blocks_traversal(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    with pytest.raises(HTTPException) as exc:
        static_file_response(tmp_path / "nested", "../outside")
    assert exc.value.status_code == 404


def test_static_file_response_blocks_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        static_file_response(tmp_path, "/etc/passwd")
    assert exc.value.status_code == 404
