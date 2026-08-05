"""Douyin API helpers for share-link download (video / album / Live Photo)."""

from .cookies import validate_cookie_header, validate_cookies
from .resolve import (
    DouyinMediaItem,
    DouyinResolveError,
    DouyinVideoResult,
    resolve_and_download,
)
from .validators import extract_douyin_urls, is_short_url, normalize_short_url

__all__ = [
    "DouyinMediaItem",
    "DouyinResolveError",
    "DouyinVideoResult",
    "extract_douyin_urls",
    "is_short_url",
    "normalize_short_url",
    "resolve_and_download",
    "validate_cookie_header",
    "validate_cookies",
]
