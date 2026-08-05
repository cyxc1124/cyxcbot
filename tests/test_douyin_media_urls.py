"""Album / Live Photo URL extraction for Douyin aweme detail."""

from __future__ import annotations

from utils.douyin_api.media_urls import (
    AlbumMediaUrl,
    extract_album_urls,
    get_content_type,
    guess_media_extension,
)


def test_content_type_video_and_album():
    assert get_content_type({"aweme_type": 0}) == "video"
    assert get_content_type({"aweme_type": 4}) == "video"
    assert get_content_type({"aweme_type": 2}) == "image"
    assert get_content_type({"aweme_type": 68}) == "image"
    assert get_content_type({"aweme_type": 999, "images": [{"url_list": ["x"]}]}) == (
        "image"
    )
    assert get_content_type({"aweme_type": 999}) == "video"


def test_extract_static_album_preserves_order():
    detail = {
        "aweme_type": 68,
        "images": [
            {"url_list": ["https://cdn.example/a.webp?x=1", "https://cdn.example/a2"]},
            {"url_list": ["https://cdn.example/b.jpg"]},
            {"download_url_list": ["https://cdn.example/c.png"]},
        ],
    }
    urls = extract_album_urls(detail)
    assert [item.kind for item in urls] == ["image", "image", "image"]
    assert [item.url for item in urls] == [
        "https://cdn.example/a.webp?x=1",
        "https://cdn.example/b.jpg",
        "https://cdn.example/c.png",
    ]


def test_extract_live_photo_uses_play_addr_as_video():
    detail = {
        "aweme_type": 68,
        "images": [
            {
                "live_photo_type": 1,
                "url_list": ["https://cdn.example/cover.jpg"],
                "video": {
                    "play_addr": {
                        "url_list": [
                            "https://cdn.example/live.mp4&watermark=1&logo_name=x"
                        ]
                    }
                },
            },
            {
                "url_list": ["https://cdn.example/static.jpg"],
            },
        ],
    }
    urls = extract_album_urls(detail)
    assert len(urls) == 2
    assert urls[0].kind == "video"
    assert urls[0].url == "https://cdn.example/live.mp4"
    assert urls[1].kind == "image"
    assert urls[1].url == "https://cdn.example/static.jpg"


def test_extract_live_via_clip_type_and_embedded_video():
    detail = {
        "images": [
            {
                "clip_type": 5,
                "video": {
                    "download_addr": {
                        "url_list": ["https://cdn.example/alt.mp4&watermark=1"]
                    }
                },
            }
        ]
    }
    urls = extract_album_urls(detail)
    assert urls == [AlbumMediaUrl(url="https://cdn.example/alt.mp4", kind="video")]


def test_guess_media_extension():
    assert guess_media_extension("https://x/a.mp4", kind="video") == ".mp4"
    assert guess_media_extension("https://x/a.webp?q=1", kind="image") == ".webp"
    assert guess_media_extension("https://x/a.jpeg", kind="image") == ".jpg"
    assert guess_media_extension("https://x/noext", kind="image") == ".jpg"
