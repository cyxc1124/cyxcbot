"""Per-target access for link-parser policies on mixed QQ adapters."""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, status

from admin.services.message_policy import visible_message_policy_rows

RosterStatus = Literal["ok", "offline", "incomplete"]


def link_parser_policy_rows(rows: list[dict], fetch_status: RosterStatus) -> list[dict]:
    return [
        {
            **row,
            "source": row.get("source", "onebot"),
            "editable": fetch_status == "ok" or row.get("source") == "official",
        }
        for row in visible_message_policy_rows(rows, fetch_status)
    ]


def ensure_link_parser_target_editable(
    target_id: str,
    rows: list[dict],
    fetch_status: RosterStatus,
    *,
    id_key: str,
    detail: str,
) -> dict:
    target_id = str(target_id)
    for row in link_parser_policy_rows(rows, fetch_status):
        if str(row[id_key]) == target_id and row["editable"]:
            return row
    # Complete OneBot lists retain policies for numeric non-friend QQ IDs.
    if fetch_status == "ok" and target_id.isdigit():
        return {id_key: target_id, "source": "onebot", "editable": True}
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
