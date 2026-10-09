"""Message allowlist edits when the OneBot roster is unavailable."""

from fastapi import HTTPException


def visible_message_policy_rows(rows: list[dict], fetch_status: str) -> list[dict]:
    return [
        row
        for row in rows
        if fetch_status != "offline" or row.get("source") == "official"
    ]


def ensure_message_policy_edit_allowed(
    *,
    fetch_status: str,
    rows: list[dict],
    id_key: str,
    current_restrict: bool,
    current_ids: list[str],
    restrict: bool,
    enabled_ids: list[str],
) -> None:
    if fetch_status == "ok":
        return
    changed_ids = set(current_ids) ^ set(enabled_ids)
    official_ids = {str(row[id_key]) for row in rows if row.get("source") == "official"}
    if (
        not current_restrict
        or restrict != current_restrict
        or not changed_ids <= official_ids
    ):
        raise HTTPException(
            status_code=503,
            detail="列表不完整，只能单独修改已发现的官方会话，不能修改其他会话或全部启用模式",
        )
