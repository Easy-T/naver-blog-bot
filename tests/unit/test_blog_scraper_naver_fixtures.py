import json
from pathlib import Path

import pytest

from naver_blog_bot.blog_scraper.adapters import naver
from naver_blog_bot.blog_scraper.adapters.html import parse_html, select_all

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
