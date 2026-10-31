"""API timestamp strings must work in ordering and every message renderer."""

import time

import pytest

from utils.bilibili_api.dynamic_api import DynamicFetcher
from utils.bilibili_api.dynamic_models import DynamicItem


@pytest.mark.parametrize(
    "timestamp,expected",
    [
        (1700000000, 1700000000),
        (1700000000.5, 1700000000.5),
        ("1700000000", 1700000000),
    ],
)
def test_dynamic_timestamp_is_numeric_and_formats_beijing_time(timestamp, expected):
    item = DynamicItem(1, 1, "作者", timestamp, 4)
    assert item.timestamp == expected
    assert isinstance(item.timestamp, (int, float))
    assert item.format_beijing_time() == "2023-11-15 06:13:20"


def test_mixed_api_timestamp_types_sort_numerically():
    items = [
        DynamicItem(1, 1, "作者", "10", 4),
        DynamicItem(2, 1, "作者", 2, 4),
        DynamicItem(3, 1, "作者", "9", 4),
    ]
    assert [item.id for item in sorted(items, key=lambda item: item.timestamp)] == [
        2,
        3,
        1,
    ]
    assert max(items, key=lambda item: item.timestamp).id == 1


@pytest.mark.skipif(
    not hasattr(time, "tzset"), reason="Host TZ override requires tzset"
)
def test_beijing_time_is_independent_of_host_timezone(monkeypatch):
    try:
        with monkeypatch.context() as environment:
            environment.setenv("TZ", "UTC")
            time.tzset()
            item = DynamicItem(1, 1, "作者", 1700000000, 4)
            assert item.format_beijing_time() == "2023-11-15 06:13:20"
    finally:
        time.tzset()


@pytest.mark.parametrize("location", ["author", "item"])
@pytest.mark.parametrize("timestamp", [1700000000, "1700000000", " 1700000000 "])
async def test_api_timestamp_normalization(location, timestamp):
    author = {"mid": 1, "name": "作者"}
    data = {
        "id_str": "1",
        "type": "DYNAMIC_TYPE_WORD",
        "modules": {"module_author": author},
    }
    (author if location == "author" else data)["pub_ts"] = timestamp
    item = await DynamicFetcher(None)._parse_dynamic_item(data, "1")
    assert item is not None
    assert item.timestamp == 1700000000
    assert item.format_beijing_time() == "2023-11-15 06:13:20"


async def test_invalid_api_timestamp_is_skipped_before_delivery():
    item = await DynamicFetcher(None)._parse_dynamic_item(
        {"id_str": "1", "pub_ts": "not-a-timestamp"}, "1"
    )
    assert item is None
