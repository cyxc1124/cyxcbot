"""视频详情保留分 P，选择分 P 不改写稿件对象。"""

import pytest

from utils.bilibili_api import VideoInfo


def test_select_page_uses_matching_cid_duration_and_url():
    video = VideoInfo.from_api_data(
        {
            "aid": 170001,
            "bvid": "BV1xx411c7mD",
            "title": "测试视频",
            "cid": 100,
            "duration": 90,
            "pages": [
                {"page": 1, "cid": 100, "part": "开场", "duration": 30},
                {"page": 2, "cid": 200, "part": "正式内容", "duration": 60},
            ],
        }
    )
    selected = video.select_page(2)
    assert (selected.cid, selected.duration, selected.page) == (200, 60, 2)
    assert selected.get_video_url().endswith("BV1xx411c7mD?p=2")
    assert (video.cid, video.duration, video.page) == (100, 90, None)
    assert video.title == selected.title == "测试视频"
    assert not video.get_video_url().endswith("?p=1")
    assert selected.to_dict()["pages"][1] == {
        "page": 2,
        "cid": 200,
        "part": "正式内容",
        "duration": 60,
    }
    with pytest.raises(ValueError, match="1～2"):
        video.select_page(3)


def test_first_page_cid_fallback_and_legacy_video_without_pages():
    video = VideoInfo.from_api_data({"pages": [{"cid": 123, "duration": 10}]})
    assert video.cid == 123
    assert video.pages[0].part == ""
    legacy = VideoInfo.from_api_data({"aid": 170001, "cid": 456})
    assert legacy.get_video_url().endswith("av170001")
    assert legacy.select_page(1).cid == 456
    assert legacy.select_page(1).get_video_url().endswith("av170001?p=1")
    with pytest.raises(ValueError, match="1～1"):
        legacy.select_page(2)
