from io import BytesIO
from unittest.mock import MagicMock

import pytest
from material_color_utilities import Hct
from PIL import Image, ImageDraw

from admin.schemas.settings import SettingsUpdateRequest
from utils.bilibili_api.dynamic_api import DynamicFetcher
from utils.bilibili_api.dynamic_models import DynamicItem
from utils.dynamic_card import _asset, _draw_card, monet_palette


def test_monet_tones_are_ordered_and_keep_seed_hue():
    palette = monet_palette(Image.new("RGB", (40, 40), "#cd9378"))
    tones = [Hct(color).tone for color in palette]
    assert tones == sorted(tones)
    assert tones == pytest.approx([65, 90, 96], abs=0.5)
    assert Hct(palette[0]).hue == pytest.approx(Hct("#cd9378").hue, abs=5)


@pytest.mark.parametrize("pictures", [[], [Image.new("RGB", (200, 120), "pink")] * 9])
def test_card_renders_chinese_and_multiline_text(pictures):
    dynamic = DynamicItem(
        123,
        1,
        "冷鸢yousa",
        1700000000,
        2,
        body_text="朋友们！明天晚上开播\n" + "长文本" * 100,
        stats={"like": 2547},
    )
    data = _draw_card(dynamic, Image.new("RGB", (100, 100), "orange"), pictures)
    with Image.open(BytesIO(data)) as result:
        assert result.width == 1040
        assert result.height > 600
        assert result.format == "PNG"


async def test_asset_rejects_non_cdn_without_request():
    session = MagicMock()
    for url in (
        "https://127.0.0.1/a",
        "file:///etc/passwd",
        "https://i0.hdslb.com.evil.org/a",
    ):
        assert await _asset(session, url) is None
    session.get.assert_not_called()


async def test_parser_keeps_card_metadata():
    item = await DynamicFetcher(None)._parse_dynamic_item(
        {
            "id_str": "123",
            "type": "DYNAMIC_TYPE_WORD",
            "modules": {
                "module_author": {
                    "mid": 1,
                    "name": "作者",
                    "face": "https://i0.hdslb.com/a",
                    "pub_ts": 1700000000,
                },
                "module_stat": {"like": {"count": 42}},
            },
        },
        "1",
    )
    assert item.avatar == "https://i0.hdslb.com/a"
    assert item.stats == {"like": 42, "comment": 0, "forward": 0}
    assert item.timestamp == 1700000000


def test_settings_validate_mode():
    assert SettingsUpdateRequest(dynamic_image_mode="card").dynamic_image_mode == "card"
    with pytest.raises(ValueError):
        SettingsUpdateRequest(dynamic_image_mode="unknown")


def test_missing_picture_falls_back_instead_of_hiding_content():
    dynamic = DynamicItem(1, 1, "作者", 1700000000, 2)
    with pytest.raises(ValueError, match="配图不完整"):
        _draw_card(dynamic, None, [None])


@pytest.mark.parametrize("prefix", ["http:", "https:", ""])
async def test_cdn_assets_always_use_https(prefix):
    session = MagicMock()
    response = session.get.return_value.__aenter__.return_value
    response.status = 404
    assert await _asset(session, prefix + "//i0.hdslb.com/bfs/new_dyn/test.png") is None
    session.get.assert_called_once_with(
        "https://i0.hdslb.com/bfs/new_dyn/test.png", allow_redirects=False
    )


@pytest.mark.parametrize(
    "source,has_avatar,has_picture,expected",
    [
        ("image", True, True, "picture"),
        ("avatar", True, True, "avatar"),
        ("image", True, False, "avatar"),
        ("avatar", False, True, "default"),
        ("image", False, False, "default"),
    ],
)
def test_card_uses_selected_color_source(
    monkeypatch, source, has_avatar, has_picture, expected
):
    import utils.dynamic_card as card

    avatar = Image.new("RGB", (20, 20), "blue") if has_avatar else None
    picture = Image.new("RGB", (20, 20), "red") if has_picture else None
    palette = MagicMock(return_value=("#667788", "#ddeeff", "#ffffff"))
    monkeypatch.setattr(card, "monet_palette", palette)
    card._draw_card(
        DynamicItem(1, 1, "作者", 1700000000, 2),
        avatar,
        [picture] if picture else [],
        source,
    )
    seed = {"picture": picture, "avatar": avatar, "default": None}[expected]
    palette.assert_called_once_with(seed)


def test_settings_validate_color_source():
    assert (
        SettingsUpdateRequest(
            dynamic_card_color_source="avatar"
        ).dynamic_card_color_source
        == "avatar"
    )
    with pytest.raises(ValueError):
        SettingsUpdateRequest(dynamic_card_color_source="invalid")


@pytest.mark.parametrize(
    "dynamic_type,title,body,expected",
    [
        (8, "视频标题", "视频标题\n视频简介", "视频简介"),
        (64, "专栏标题", "正文&nbsp;内容 &amp; 更多", "正文 内容 & 更多"),
    ],
)
def test_card_text_has_no_duplicate_title_or_article_entities(
    monkeypatch, dynamic_type, title, body, expected
):
    drawn = []
    original = ImageDraw.ImageDraw.text

    def record(draw, xy, text, *args, **kwargs):
        drawn.append(text)
        return original(draw, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", record)
    _draw_card(
        DynamicItem(
            1, 1, "作者", 1700000000, dynamic_type, title=title, body_text=body
        ),
        None,
        [],
    )
    assert drawn.count(title) == 1
    assert expected in drawn
    assert "&nbsp;" not in "".join(drawn)
