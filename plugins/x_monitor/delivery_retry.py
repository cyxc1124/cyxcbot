"""Helpers for partial X notification delivery retries."""

from __future__ import annotations

from shared.notify.delivery import DeliveryResult


def failed_target_ids(delivery: DeliveryResult) -> tuple[list[str], list[str]]:
    """Backward-compatible: failed target ids without resume offsets."""
    groups, users = failed_targets_with_resume(delivery)
    return [gid for gid, _ in groups], [uid for uid, _ in users]


def failed_targets_with_resume(
    delivery: DeliveryResult,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Failed targets with batch resume index (0 = from start)."""
    groups: list[tuple[str, int]] = []
    users: list[tuple[str, int]] = []
    for target in delivery.targets:
        if target.success:
            continue
        resume = parse_resume_from(target.error)
        item = (target.target_id, resume)
        if target.target_type == "group":
            groups.append(item)
        elif target.target_type == "user":
            users.append(item)
    return groups, users


def parse_resume_from(error: str | None) -> int:
    raw = str(error or "")
    if not raw.startswith("resume_from:"):
        return 0
    rest = raw.split(":", 2)
    if len(rest) < 2:
        return 0
    try:
        return max(0, int(rest[1]))
    except ValueError:
        return 0


def batch_plan_fingerprint(batch_kinds: list[str], *, at_all: bool = False) -> str:
    """Stable fingerprint from per-batch kind strings (e.g. ``tti``, ``v``)."""
    parts: list[str] = []
    if at_all:
        parts.append("a")
    for kind in batch_kinds:
        parts.append(str(kind or "e"))
    return "|".join(parts)


def normalize_batch_start(
    start: int,
    batch_count: int,
    *,
    expected_fingerprint: str = "",
    actual_fingerprint: str = "",
) -> tuple[bool, int, str | None]:
    """校验续传下标 / 投递计划指纹。

    返回 (可以发送, 起始下标, 失败时的 error)。
    """
    try:
        start = max(0, int(start))
    except TypeError, ValueError:
        start = 0
    expected = (expected_fingerprint or "").strip()
    actual = (actual_fingerprint or "").strip()
    if expected and actual and expected != actual:
        return (
            False,
            0,
            f"resume_from:0:stale_plan:{expected}->{actual}",
        )
    if batch_count <= 0:
        return True, 0, None
    if start > 0 and start >= batch_count:
        return (
            False,
            0,
            f"resume_from:0:stale_batches:{start}/{batch_count}",
        )
    return True, start, None


def encode_pending_tweet_ref(tweet_id: str, fingerprint: str = "") -> str:
    tid = str(tweet_id or "").strip()
    fp = str(fingerprint or "").strip().replace("#", "")
    if not tid:
        return ""
    if not fp:
        return tid
    return f"{tid}#{fp}"


def decode_pending_tweet_ref(raw: str | None) -> tuple[str, str]:
    s = str(raw or "").strip()
    if not s:
        return "", ""
    if "#" in s:
        tid, _, fp = s.partition("#")
        return tid.strip(), fp.strip()
    return s, ""


def encode_pending_ids(ids: list[str]) -> str:
    return ",".join(id_ for id_ in ids if id_)


def decode_pending_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part for part in str(raw).split(",") if part]


def encode_pending_targets(targets: list[tuple[str, int]]) -> str:
    parts: list[str] = []
    for target_id, start in targets:
        tid = str(target_id or "").strip()
        if not tid:
            continue
        try:
            idx = max(0, int(start))
        except TypeError, ValueError:
            idx = 0
        parts.append(f"{tid}@{idx}" if idx else tid)
    return ",".join(parts)


def decode_pending_targets(raw: str | None) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for part in decode_pending_ids(raw):
        if "@" in part:
            tid, _, idx_raw = part.partition("@")
            tid = tid.strip()
            if not tid:
                continue
            try:
                result.append((tid, max(0, int(idx_raw))))
            except ValueError:
                result.append((tid, 0))
        else:
            result.append((part, 0))
    return result
