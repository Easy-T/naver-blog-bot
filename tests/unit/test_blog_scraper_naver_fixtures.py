import json
from pathlib import Path

import pytest

from naver_blog_bot.blog_scraper.adapters import naver
from naver_blog_bot.blog_scraper.adapters.html import parse_html, select_all
from naver_blog_bot.blog_scraper.adapters.naver import parse_post_html
from naver_blog_bot.blog_scraper.models import EmoticonBlock, ImageBlock, TextBlock

_FIXTURES = Path(__file__).parent / "fixtures" / "naver"
_BASE = naver.post_list_url("https://blog.naver.com/flowerbend")


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _hrefs_from_html(html: str) -> list[str]:
    root = parse_html(html)
    return [a.attrs.get("href", "") for a in select_all(root, "a")]


# --- rendered mobile-home DOM (categoryNo absent -> live-DOM anchor path) ---


def test_mobile_home_fixture_extracts_unique_post_urls() -> None:
    hrefs = _hrefs_from_html(_load("mobile_home.html"))
    urls = naver._select_post_hrefs(hrefs, _BASE, 10)
    assert urls == [
        "https://m.blog.naver.com/flowerbend/223456789",
        "https://m.blog.naver.com/flowerbend/223456700",
        "https://m.blog.naver.com/flowerbend/223456611",
        "https://m.blog.naver.com/flowerbend/223456500",
    ]


def test_mobile_home_fixture_respects_count() -> None:
    hrefs = _hrefs_from_html(_load("mobile_home.html"))
    urls = naver._select_post_hrefs(hrefs, _BASE, 2)
    assert urls == [
        "https://m.blog.naver.com/flowerbend/223456789",
        "https://m.blog.naver.com/flowerbend/223456700",
    ]


def test_mobile_home_empty_fixture_returns_no_urls() -> None:
    hrefs = _hrefs_from_html(_load("mobile_home_empty.html"))
    assert naver._select_post_hrefs(hrefs, _BASE, 10) == []


# --- PostTitleListAsync JSON (categoryNo present -> JSON API path) ---


def test_posttitlelist_category_fixture_extracts_urls() -> None:
    payload = naver._parse_naver_json(_load("posttitlelist_category.json"))
    urls = naver._select_post_urls_from_titlelist(payload, "flowerbend", 10)
    assert urls == [
        "https://m.blog.naver.com/flowerbend/223456789",
        "https://m.blog.naver.com/flowerbend/223456700",
        "https://m.blog.naver.com/flowerbend/223456611",
    ]


def test_posttitlelist_category_fixture_respects_count() -> None:
    payload = naver._parse_naver_json(_load("posttitlelist_category.json"))
    urls = naver._select_post_urls_from_titlelist(payload, "flowerbend", 2)
    assert urls == [
        "https://m.blog.naver.com/flowerbend/223456789",
        "https://m.blog.naver.com/flowerbend/223456700",
    ]


def test_posttitlelist_paginghtml_fixture_recovers_via_regex() -> None:
    raw = _load("posttitlelist_paginghtml.json")
    # Confirm the fixture really is the broken-shape case (invalid \' escape).
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw)
    payload = naver._parse_naver_json(raw)
    urls = naver._select_post_urls_from_titlelist(payload, "flowerbend", 10)
    assert urls == [
        "https://m.blog.naver.com/flowerbend/224291881837",
        "https://m.blog.naver.com/flowerbend/224141677589",
    ]


def test_posttitlelist_empty_fixture_returns_no_urls() -> None:
    payload = naver._parse_naver_json(_load("posttitlelist_empty.json"))
    assert naver._select_post_urls_from_titlelist(payload, "flowerbend", 10) == []


def test_posttitlelist_garbage_fixture_raises_clear_error() -> None:
    raw = _load("posttitlelist_garbage.json")
    with pytest.raises(ValueError, match="invalid JSON"):
        naver._parse_naver_json(raw)


# --- SmartEditor ONE post body (parse_post_html .se-main-container path) ---


def test_post_smarteditor_fixture_block_order_and_classification() -> None:
    doc = parse_post_html(
        _load("post_smarteditor.html"), "https://m.blog.naver.com/flowerbend/223456789"
    )
    assert doc.title == "플라워벤드 봄 신상 원피스 솔직 후기"
    assert [type(b) for b in doc.blocks] == [
        TextBlock,
        ImageBlock,
        EmoticonBlock,
        TextBlock,
        EmoticonBlock,
    ]
    assert doc.blocks[1].alt == "민트색 원피스 정면 컷"
    assert doc.blocks[3].content == "색감이 화면보다 실물이 훨씬 예뻐요!"


def test_post_smarteditor_fixture_collapses_multiparagraph_text() -> None:
    doc = parse_post_html(
        _load("post_smarteditor.html"), "https://m.blog.naver.com/flowerbend/223456789"
    )
    # Two <p> inside one se-text component collapse to ONE whitespace-joined TextBlock.
    assert doc.blocks[0].content == (
        "안녕하세요, 플라워벤드입니다. 오늘은 봄 신상 원피스를 소개할게요."
    )


def test_post_smarteditor_fixture_detects_emoticons_two_ways() -> None:
    doc = parse_post_html(
        _load("post_smarteditor.html"), "https://m.blog.naver.com/flowerbend/223456789"
    )
    # blocks[2]: se-sticker COMPONENT class -> emoticon (src is an OGQ CDN url that
    # does NOT match the URL patterns, so only the component-class path catches it).
    assert isinstance(doc.blocks[2], EmoticonBlock)
    assert doc.blocks[2].description == "설레는 표정"
    # blocks[4]: se-image whose img src matches "static/se/sticker" URL pattern.
    assert isinstance(doc.blocks[4], EmoticonBlock)
    assert doc.blocks[4].description == "하트뿅뿅"


def test_post_smarteditor_empty_fixture_returns_no_blocks() -> None:
    doc = parse_post_html(
        _load("post_smarteditor_empty.html"),
        "https://m.blog.naver.com/flowerbend/1",
    )
    # Container present, but only an empty se-text + a non-se-component sibling:
    # graceful empty block list, NOT a crash.
    assert doc.title == "빈 본문 테스트"
    assert doc.blocks == []


# --- Legacy #postViewArea body + unsupported structure ---


def test_post_legacy_fixture_block_order_and_classification() -> None:
    doc = parse_post_html(
        _load("post_legacy.html"), "https://m.blog.naver.com/flowerbend/1"
    )
    assert doc.title == "2019년 가을 제주 여행 기록"
    assert [type(b) for b in doc.blocks] == [
        TextBlock,
        ImageBlock,
        TextBlock,
        ImageBlock,
        EmoticonBlock,
        TextBlock,
    ]
    assert doc.blocks[0].content == "제주도에 다녀왔습니다."
    assert doc.blocks[1].alt == "제주 바다"
    assert doc.blocks[3].alt == "제주 카페"
    assert doc.blocks[4].description == "신난 표정"
    assert doc.blocks[5].content == "다음에 또 가고 싶어요."


def test_post_unsupported_fixture_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="unsupported Naver post structure"):
        parse_post_html(
            _load("post_unsupported.html"), "https://m.blog.naver.com/flowerbend/1"
        )
