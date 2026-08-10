"""Tests for X media variant / item parsing."""

from __future__ import annotations

from utils.x_api.media import media_items_for_tweet, pick_mp4_variant


def test_pick_mp4_variant_highest_bitrate():
    media = {
        "type": "video",
        "variants": [
            {
                "content_type": "application/x-mpegURL",
                "url": "https://example/master.m3u8",
            },
            {
                "bit_rate": 832000,
                "content_type": "video/mp4",
                "url": "https://example/low.mp4",
            },
            {
                "bit_rate": 2176000,
                "content_type": "video/mp4",
                "url": "https://example/high.mp4",
            },
        ],
    }
    assert pick_mp4_variant(media) == "https://example/high.mp4"


def test_pick_mp4_variant_empty():
    assert pick_mp4_variant({"type": "video", "variants": []}) is None
    assert pick_mp4_variant({"type": "photo"}) is None


def test_media_items_video_and_photo():
    tweet = {"attachments": {"media_keys": ["m1", "m2", "m3"]}}
    by_key = {
        "m1": {
            "type": "video",
            "preview_image_url": "https://example/preview.jpg",
            "variants": [
                {
                    "bit_rate": 1000,
                    "content_type": "video/mp4",
                    "url": "https://example/v.mp4",
                }
            ],
        },
        "m2": {"type": "photo", "url": "https://example/p.jpg"},
        "m3": {
            "type": "animated_gif",
            "variants": [
                {"content_type": "video/mp4", "url": "https://example/gif.mp4"}
            ],
        },
    }
    items = media_items_for_tweet(tweet, by_key)
    assert [(i.kind, i.url) for i in items] == [
        ("video", "https://example/v.mp4"),
        ("image", "https://example/p.jpg"),
        ("video", "https://example/gif.mp4"),
    ]


def test_media_items_video_without_variant_falls_back_to_preview():
    tweet = {"attachments": {"media_keys": ["m1"]}}
    by_key = {
        "m1": {
            "type": "video",
            "preview_image_url": "https://example/preview.jpg",
            "variants": [],
        }
    }
    items = media_items_for_tweet(tweet, by_key)
    assert len(items) == 1
    assert items[0].kind == "image"
    assert items[0].url == "https://example/preview.jpg"
