"""Official cache access must not unlock an incomplete OneBot roster."""

import pytest
from fastapi import HTTPException

from admin.services.link_parser_access import (
    ensure_link_parser_target_editable,
    link_parser_policy_rows,
)


@pytest.mark.parametrize("fetch_status", ["ok", "offline", "incomplete"])
def test_cached_official_target_stays_editable(fetch_status):
    row = {"group_id": "official-openid", "source": "official"}
    assert ensure_link_parser_target_editable(
        "official-openid", [row], fetch_status, id_key="group_id", detail="read only"
    )["editable"]


@pytest.mark.parametrize("fetch_status", ["offline", "incomplete"])
@pytest.mark.parametrize("target_id", ["123", "unknown-openid"])
def test_partial_roster_rejects_nonofficial_or_unknown_target(fetch_status, target_id):
    with pytest.raises(HTTPException) as error:
        ensure_link_parser_target_editable(
            target_id,
            [{"user_id": "123", "source": "onebot"}],
            fetch_status,
            id_key="user_id",
            detail="read only",
        )
    assert error.value.status_code == 503


def test_offline_list_keeps_only_cached_official_targets():
    rows = [
        {"user_id": "123", "source": "onebot"},
        {"user_id": "known-openid", "source": "official"},
    ]
    assert link_parser_policy_rows(rows, "offline") == [
        {"user_id": "known-openid", "source": "official", "editable": True}
    ]
    assert [row["editable"] for row in link_parser_policy_rows(rows, "incomplete")] == [
        False,
        True,
    ]


def test_complete_roster_preserves_numeric_nonfriend_and_rejects_unknown_openid():
    assert ensure_link_parser_target_editable(
        "123", [], "ok", id_key="user_id", detail="read only"
    ) == {"user_id": "123", "source": "onebot", "editable": True}
    with pytest.raises(HTTPException):
        ensure_link_parser_target_editable(
            "unknown-openid", [], "ok", id_key="user_id", detail="read only"
        )
