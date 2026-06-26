"""Tests for Web Admin log broadcast setup."""

from __future__ import annotations

import logging

from shared.logging.broadcast import install_log_broadcast


def test_install_log_broadcast_does_not_attach_uvicorn_handlers() -> None:
    """Stdlib uvicorn logs should reach Web /logs via LoguruHandler only."""
    install_log_broadcast()
    for name in ("uvicorn", "uvicorn.error"):
        assert not logging.getLogger(name).handlers
