"""Target ID routing. ponytail: no platform column; all-digit openid would collide."""

import re


def is_numeric_qq_id(target_id: str) -> bool:
    return str(target_id).strip().isdigit()


def onebot_target_ids(target_ids: list[str]) -> list[str]:
    """官方群/C2C 仅支持被动回复，不参与后台主动投递。"""
    return [target_id for target_id in target_ids if is_numeric_qq_id(target_id)]


def is_qq_user_id(user_id: str) -> bool:
    return re.fullmatch(r"(?:[0-9]+|[A-Za-z0-9_-]{8,64})", user_id.strip()) is not None
