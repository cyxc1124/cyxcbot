"""OneBot send_*_msg 返回值成功判定。"""

from __future__ import annotations


def _nonzero_message_id(mid: object) -> bool:
    """LuckyLilliaBot ``createMsgShortId`` = ``md5.readInt32BE()``（有符号 int32），负值有效。"""
    if mid is None:
        return False
    if isinstance(mid, bool):
        return mid
    if isinstance(mid, int):
        return mid != 0
    return str(mid).strip() != ""


def is_onebot_send_success(send_result: object) -> bool:
    """True when send API returned a usable message_id (file already accepted)."""
    if send_result is None:
        return False
    if isinstance(send_result, bool):
        return send_result
    if isinstance(send_result, int):
        return _nonzero_message_id(send_result)
    if isinstance(send_result, str):
        return send_result.strip() != ""

    if isinstance(send_result, dict):
        mid = send_result.get("message_id")
    else:
        mid = getattr(send_result, "message_id", None)
    return _nonzero_message_id(mid)
