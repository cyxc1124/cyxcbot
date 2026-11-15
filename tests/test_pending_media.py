"""待投递消息的大块媒体落盘，数据库只存引用。"""

import json
import os
import time

import pytest
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from shared.notify import pending_media
from shared.notify.delivery import PendingDelivery


@pytest.fixture(autouse=True)
def media_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(pending_media, "PENDING_MEDIA_DIR", tmp_path / "pm")
    monkeypatch.setattr(pending_media, "_last_prune", 0.0)
    return tmp_path / "pm"


def _pending(image: bytes) -> PendingDelivery:
    message = Message([MessageSegment.text("hi"), MessageSegment.image(image)])
    return PendingDelivery(message, ["1"], [])


def test_large_image_is_stored_as_file_reference(media_dir):
    image = os.urandom(20_000)
    data = _pending(image).to_data()

    assert "base64://" not in json.dumps(data)
    assert len(json.dumps(data)) < 1000
    assert len(list(media_dir.iterdir())) == 1

    restored = PendingDelivery.from_data(data)
    assert restored.message == _pending(image).message


def test_same_image_is_written_once(media_dir):
    image = os.urandom(20_000)
    _pending(image).to_data()
    _pending(image).to_data()
    assert len(list(media_dir.iterdir())) == 1


def test_small_media_stays_inline(media_dir):
    data = _pending(b"tiny").to_data()
    assert "base64://" in json.dumps(data)
    assert not media_dir.exists()


def test_legacy_inline_state_still_loads():
    legacy = _pending(os.urandom(20_000))
    raw = {
        "message": [{"type": s.type, "data": s.data} for s in legacy.message],
        "groups": ["1"],
        "users": [],
        "at_all": False,
        "group_starts": {},
        "user_starts": {},
    }
    assert PendingDelivery.from_data(raw).message == legacy.message


def test_missing_file_drops_only_that_segment(media_dir):
    data = _pending(os.urandom(20_000)).to_data()
    for path in media_dir.iterdir():
        path.unlink()
    restored = PendingDelivery.from_data(data)
    assert [segment.type for segment in restored.message] == ["text"]


def test_tampered_reference_is_not_read_as_path():
    data = _pending(os.urandom(20_000)).to_data()
    data["message"][1]["data"]["file"] = "pending-media://../../etc/passwd"
    restored = PendingDelivery.from_data(data)
    assert [segment.type for segment in restored.message] == ["text"]


def test_old_files_are_pruned_and_live_ones_kept(media_dir):
    old = os.urandom(20_000)
    _pending(old).to_data()
    (old_file,) = media_dir.iterdir()
    stale = time.time() - pending_media._PRUNE_AGE_SECONDS - 60
    os.utime(old_file, (stale, stale))
    pending_media._last_prune = 0.0

    fresh = os.urandom(20_000)
    _pending(fresh).to_data()

    names = {path.name for path in media_dir.iterdir()}
    assert old_file.name not in names
    assert len(names) == 1


def test_missing_directory_is_not_an_error(media_dir, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        pending_media.logger, "opt", lambda **_: pytest.fail("不应打印异常堆栈")
    )
    monkeypatch.setattr(
        pending_media.logger, "warning", lambda *a, **k: warnings.append(a)
    )
    # 纯文字消息 + 目录尚未创建：首次持久化也会走清理。
    PendingDelivery(Message("text only"), ["1"], []).to_data()
    assert warnings == []
    assert not media_dir.exists()


def test_stale_crash_leftover_tmp_is_pruned_but_fresh_one_is_kept(media_dir):
    media_dir.mkdir()
    stale_tmp = media_dir / ("a" * 64 + ".tmp")
    fresh_tmp = media_dir / ("b" * 64 + ".tmp")
    unrelated = media_dir / "notes.txt"
    for path in (stale_tmp, fresh_tmp, unrelated):
        path.write_bytes(b"x")
    stale = time.time() - pending_media._PRUNE_AGE_SECONDS - 60
    for path in (stale_tmp, unrelated):
        os.utime(path, (stale, stale))

    _pending(os.urandom(20_000)).to_data()

    names = {path.name for path in media_dir.iterdir()}
    assert stale_tmp.name not in names
    assert fresh_tmp.name in names
    assert unrelated.name in names  # 只清理自己生成的文件
