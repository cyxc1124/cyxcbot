"""Pure-function tests for utils.douyin_api validators / cookies / URLs."""

from __future__ import annotations

from utils.douyin_api.cookies import validate_cookie_header, validate_cookies
from utils.douyin_api.url_parser import extract_video_id, parse_video_url
from utils.douyin_api.validators import (
    extract_douyin_urls,
    is_short_url,
    normalize_short_url,
    parse_url_type,
)
from utils.douyin_api.video_urls import (
    build_video_url_candidates,
    is_watermarked_media_url,
    pick_preferred_play_addr,
)
from utils.douyin_api.xbogus import generate_x_bogus


class _FakeClient:
    BASE_URL = "https://www.douyin.com"
    headers = {"User-Agent": "test-ua"}

    def sign_url(self, url: str) -> tuple[str, str]:
        return f"{url}&X-Bogus=fake", "test-ua"

    def build_signed_path(self, path: str, params: dict, **_kwargs) -> tuple[str, str]:
        from urllib.parse import urlencode

        return f"{self.BASE_URL}{path}?{urlencode(params)}&X-Bogus=fake", "test-ua"


def test_extract_douyin_urls_from_share_text():
    text = "6.66 复制打开抖音，看看【作者】的作品 https://v.douyin.com/AbCdEf/ 嗨"
    urls = extract_douyin_urls(text)
    assert urls == ["https://v.douyin.com/AbCdEf/"]


def test_is_short_url_and_normalize():
    assert is_short_url("v.douyin.com/xxx")
    assert is_short_url("https://v.douyin.com/xxx")
    assert not is_short_url("https://www.douyin.com/video/1")
    assert normalize_short_url("v.douyin.com/xxx") == "https://v.douyin.com/xxx"


def test_parse_url_type_and_video_id():
    assert parse_url_type("https://v.douyin.com/abc") == "short"
    video = "https://www.douyin.com/video/7123456789012345678"
    assert parse_url_type(video) == "video"
    assert extract_video_id(video) == "7123456789012345678"
    modal = "https://www.douyin.com/user/xxx?modal_id=7123456789012345678"
    assert parse_url_type(modal) == "video"
    parsed = parse_video_url(modal)
    assert parsed is not None
    assert parsed["aweme_id"] == "7123456789012345678"


def test_validate_cookies_required_keys():
    assert validate_cookies(
        {
            "ttwid": "1",
            "odin_tt": "2",
            "passport_csrf_token": "3",
        }
    )
    assert not validate_cookie_header("ttwid=1; sessionid=x")


def test_xbogus_appends_param():
    signed, value, ua = generate_x_bogus(
        "https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id=1"
    )
    assert "X-Bogus=" in signed
    assert value
    assert ua


def test_is_watermarked_and_candidates_prefer_direct_cdn():
    assert is_watermarked_media_url("https://example.com/playwm/xxx")
    assert not is_watermarked_media_url("https://cdn.example.com/video.mp4?watermark=0")

    aweme = {
        "video": {
            "bit_rate": [
                {
                    "bit_rate": 1000,
                    "play_addr": {
                        "uri": "v123",
                        "width": 1080,
                        "height": 1920,
                        "url_list": [
                            "https://www.douyin.com/aweme/v1/play/?video_id=v123&watermark=0",
                            "https://v3-dy.douyinvod.com/video.mp4?watermark=0",
                        ],
                    },
                }
            ]
        }
    }
    preferred = pick_preferred_play_addr(aweme["video"])
    assert preferred is not None
    candidates = build_video_url_candidates(_FakeClient(), aweme)  # type: ignore[arg-type]
    assert candidates
    assert candidates[0][0].startswith("https://v3-dy.douyinvod.com/")
