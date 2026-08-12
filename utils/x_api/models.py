"""X (Twitter) API data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal


@dataclass
class XUser:
    """X user profile."""

    id: str
    username: str
    name: str = ""


@dataclass
class TweetMediaItem:
    """One media attachment; video/gif need local file for QQ video segment."""

    kind: Literal["image", "video"]
    url: str
    file_path: Path | None = None


@dataclass
class TweetItem:
    """Single tweet for monitor push."""

    id: str
    text: str
    created_at: str
    username: str
    name: str
    url: str
    media_urls: List[str] = field(default_factory=list)
    media_items: List[TweetMediaItem] = field(default_factory=list)

    def format_time(self) -> str:
        """Format created_at to local-readable string; fall back to raw value."""
        raw = (self.created_at or "").strip()
        if not raw:
            return ""
        try:
            # X API: 2020-01-01T00:00:00.000Z
            normalized = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local = dt.astimezone()
            return local.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return raw


def tweet_id_as_int(tweet_id: str | int | None) -> int:
    """Parse snowflake tweet id for comparison; invalid values become 0."""
    if tweet_id is None:
        return 0
    try:
        return int(str(tweet_id).strip() or "0")
    except TypeError, ValueError:
        return 0
