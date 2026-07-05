"""Tests for shared.security.database_url."""

from shared.security.database_url import mask_database_url


def test_mask_database_url_hides_password() -> None:
    url = "postgresql+asyncpg://dbuser:secret-pass@db.example.com:5432/cyxcbot"
    assert mask_database_url(url) == (
        "postgresql+asyncpg://dbuser:***@db.example.com:5432/cyxcbot"
    )


def test_mask_database_url_sqlite_unchanged() -> None:
    url = "sqlite+aiosqlite:///data/cyxcbot.db"
    assert mask_database_url(url) == url
