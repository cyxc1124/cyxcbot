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


def normalize_batch_start(start: int, batch_count: int) -> tuple[bool, int, str | None]:
    """校验续传下标与当前批次数是否匹配。

    返回 (可以发送, 起始下标, 失败时的 error)。
    重试时若媒体变少导致 start 落在末尾之外/恰等于长度，空循环会被当成成功；
    此时应失败并建议从头重试（resume_from:0）。
    """
    try:
        start = max(0, int(start))
    except TypeError, ValueError:
        start = 0
    if batch_count <= 0:
        return True, 0, None
    if start > 0 and start >= batch_count:
        return (
            False,
            0,
            f"resume_from:0:stale_batches:{start}/{batch_count}",
        )
    return True, start, None


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
