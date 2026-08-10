"""X 监控检查阶段的纯状态转换逻辑（可单测）。"""

from typing import Any, List, Optional, Sequence

from utils.x_api.models import tweet_id_as_int


def collect_new_tweets(
    tweets: Sequence[Any],
    last_tweet_id: str | int,
) -> List[Any]:
    """收集 ID（按 int 比较）大于 last_tweet_id 的新推文。"""
    last_id = tweet_id_as_int(last_tweet_id)
    return [tweet for tweet in tweets if tweet_id_as_int(tweet.id) > last_id]


def compute_first_baseline_last_id(
    tweets: Sequence[Any],
) -> Optional[str]:
    """首次基准记录时写入的 last_tweet_id；无推文时返回 None。"""
    if not tweets:
        return None
    return str(max(tweets, key=lambda t: tweet_id_as_int(t.id)).id)


def should_initialize_after_first_poll(baseline: Optional[str]) -> bool:
    """空时间线不得标记已初始化（否则零游标翻页会把历史帖当新帖）。"""
    return baseline is not None


def should_fill_display_name(existing: str | None) -> bool:
    """轮询回写时仅在显示名为空时填充，不覆盖管理员手动名称。"""
    return not (existing or "").strip()
