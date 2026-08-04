"""OneBot send_*_msg 返回值成功判定。"""

from __future__ import annotations


def is_onebot_send_success(send_result: object) -> bool:
    """True when send API returned a usable message_id (file already accepted)."""
    if send_result is None:
        return False
    if isinstance(send_result, bool):
        return send_result
    if isinstance(send_result, int):
        return send_result > 0
    if isinstance(send_result, str):
        return send_result.strip() != ""

    mid = None
    if isinstance(send_result, dict):
        mid = send_result.get("message_id")
    else:
        mid = getattr(send_result, "message_id", None)

    if mid is None:
        return False
    if isinstance(mid, bool):
        return mid
    if isinstance(mid, int):
        return mid > 0
    return str(mid).strip() != ""
