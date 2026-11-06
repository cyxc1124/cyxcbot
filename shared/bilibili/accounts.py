"""Encrypted Bilibili accounts and process-wide HTTP request rotation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from itertools import count

from shared.security.crypto import decrypt_value, encrypt_value


@dataclass(frozen=True)
class BilibiliAccount:
    uid: str
    cookie: str = field(repr=False)
    username: str | None = None


def load_accounts(
    encrypted: str, legacy_encrypted: str = ""
) -> tuple[BilibiliAccount, ...]:
    if not encrypted:
        cookie = decrypt_value(legacy_encrypted)
        if not cookie:
            return ()
        pairs = dict(
            part.strip().split("=", 1) for part in cookie.split(";") if "=" in part
        )
        uid = pairs.get("DedeUserID", "")
        return (BilibiliAccount(uid if uid.isdigit() else "legacy", cookie),)

    data = json.loads(decrypt_value(encrypted))
    if not isinstance(data, list):
        raise ValueError("Invalid Bilibili account list")
    accounts = []
    for row in data:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("uid"), str)
            or not (row["uid"].isdigit() or row["uid"] == "legacy")
            or not isinstance(row.get("cookie"), str)
            or not row["cookie"].strip()
            or (
                row.get("username") is not None and not isinstance(row["username"], str)
            )
            or any(account.uid == row["uid"] for account in accounts)
        ):
            raise ValueError("Invalid Bilibili account entry")
        accounts.append(BilibiliAccount(row["uid"], row["cookie"], row.get("username")))
    return tuple(accounts)


def encrypt_accounts(accounts: tuple[BilibiliAccount, ...]) -> str:
    return encrypt_value(json.dumps([asdict(account) for account in accounts]))


class BilibiliAccountPool:
    def __init__(self) -> None:
        self._accounts: tuple[BilibiliAccount, ...] | None = None
        self._next = count()

    def configure(self, accounts: tuple[BilibiliAccount, ...]) -> None:
        if accounts != self._accounts:
            self._accounts = accounts
            self._next = count()

    def select_cookie(self, fallback: str | None = None) -> str:
        # 配置尚未加载时保留独立 API 调用方传入的 Cookie。
        if self._accounts is None:
            return fallback or ""
        if not self._accounts:
            return ""
        return self._accounts[next(self._next) % len(self._accounts)].cookie


bilibili_account_pool = BilibiliAccountPool()
