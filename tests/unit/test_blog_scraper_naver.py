import asyncio

import pytest

from naver_blog_bot.blog_scraper.adapters.naver import (
    collect_blog_post_urls,
    collect_post_urls,
    is_blog_url,
    is_emoticon_img_attrs,
    normalize_naver_url,
    parse_post_html,
    post_list_url,
    scrape_post,
)
from naver_blog_bot.blog_scraper.models import EmoticonBlock, ImageBlock, TextBlock


NAVER_SMARTEDITOR_HTML = """
<html>
<head><title>포포몬 첫 사용 후기 : 네이버 블로그</title></head>
<body>
  <div class="se-main-container">
    <div class="se-component se-text"><p>오늘 드디어 써봤는데요.</p></div>
    <div class="se-component se-image"><img src="https://postfiles.pstatic.net/photo.jpg" alt="제품 사진"></div>
    <div class="se-component se-text"><p>첫인상은 생각보다 훨씬 좋았어요!</p></div>
    <div class="se-component se-sticker"><img class="se-sticker-image" src="https://storep-phinf.pstatic.net/ogq/me/sticker.png" alt="만족하는 표정"></div>
    <div class="se-component se-image"><img src="https://postfiles.pstatic.net/photo2.jpg" alt="상세 사진"></div>
  </div>
</body>
</html>
"""


NAVER_LEGACY_HTML = """
<html>
<head><title>예전 글 : 네이버 블로그</title></head>
<body>
  <div id="postViewArea">
    <p>레거시 본문입니다.</p>
    <img src="https://postfiles.pstatic.net/legacy.jpg" alt="레거시 사진">
    <img class="emoticon" src="https://example.com/unknown.png" alt="웃는 표정">
  </div>
</body>
</html>
"""


POST_LIST_HTML = """
<html><body>
  <a href="/myid/223456789">첫 번째 글</a>
  <a href="https://m.blog.naver.com/myid/223456790">두 번째 글</a>
  <a href="/PostView.naver?blogId=myid&logNo=223456791">세 번째 글</a>
  <a href="/myid/category">카테고리</a>
</body></html>
"""


def test_normalize_naver_url_converts_pc_to_mobile() -> None:
    assert (
        normalize_naver_url("https://blog.naver.com/myid")
        == "https://m.blog.naver.com/myid"
    )
    assert (
        normalize_naver_url("https://blog.naver.com/myid/223456789")
        == "https://m.blog.naver.com/myid/223456789"
    )
    assert (
        normalize_naver_url("https://m.blog.naver.com/myid/223456789")
        == "https://m.blog.naver.com/myid/223456789"
    )


def test_is_blog_url_distinguishes_blog_index_from_post() -> None:
    assert is_blog_url("https://blog.naver.com/myid") is True
    assert is_blog_url("https://m.blog.naver.com/myid") is True
    assert is_blog_url("https://blog.naver.com/myid/223456789") is False
    assert (
        is_blog_url(
            "https://m.blog.naver.com/PostView.naver?blogId=myid&logNo=223456789"
        )
        is False
    )


def test_post_list_url_builds_mobile_post_list_url() -> None:
    assert (
        post_list_url("https://blog.naver.com/myid")
        == "https://m.blog.naver.com/PostList.naver?blogId=myid&currentPage=1"
    )


def test_parse_smarteditor_blocks_in_document_order() -> None:
    document = parse_post_html(
        NAVER_SMARTEDITOR_HTML, "https://m.blog.naver.com/myid/223456789"
    )

    assert document.title == "포포몬 첫 사용 후기"
    assert [type(block) for block in document.blocks] == [
        TextBlock,
        ImageBlock,
        TextBlock,
        EmoticonBlock,
        ImageBlock,
    ]
    assert document.blocks[0].content == "오늘 드디어 써봤는데요."
    assert document.blocks[1].alt == "제품 사진"
    assert document.blocks[3].description == "만족하는 표정"


def test_parse_legacy_post_view_area_fallback() -> None:
    document = parse_post_html(NAVER_LEGACY_HTML, "https://m.blog.naver.com/myid/1")

    assert document.title == "예전 글"
    assert [type(block) for block in document.blocks] == [
        TextBlock,
        ImageBlock,
        EmoticonBlock,
    ]
    assert document.blocks[0].content == "레거시 본문입니다."
    assert document.blocks[2].description == "웃는 표정"


def test_emoticon_detection_uses_url_patterns_and_css_keywords() -> None:
    assert (
        is_emoticon_img_attrs("https://storep-phinf.pstatic.net/ogq/me/sticker.png", "")
        is True
    )
    assert (
        is_emoticon_img_attrs("https://example.com/static/se/sticker/1.png", "") is True
    )
    assert (
        is_emoticon_img_attrs("https://example.com/image.png", "se-emoticon-image")
        is True
    )
    assert (
        is_emoticon_img_attrs("https://postfiles.pstatic.net/photo.jpg", "se-image")
        is False
    )


def test_collect_post_urls_from_mobile_post_list() -> None:
    urls = collect_post_urls(
        POST_LIST_HTML,
        "https://m.blog.naver.com/PostList.naver?blogId=myid&currentPage=1",
        count=2,
    )

    assert urls == [
        "https://m.blog.naver.com/myid/223456789",
        "https://m.blog.naver.com/myid/223456790",
    ]


def test_parse_post_html_raises_on_unsupported_structure() -> None:
    html = "<html><body><div>no known containers here</div></body></html>"
    with pytest.raises(ValueError, match="unsupported Naver post structure"):
        parse_post_html(html, "https://m.blog.naver.com/myid/1")


def test_is_emoticon_img_attrs_case_insensitive() -> None:
    assert is_emoticon_img_attrs("https://example.com/OGQ/me/sticker.png", "") is True
    assert (
        is_emoticon_img_attrs("https://example.com/photo.jpg", "SE-Emoticon-Image")
        is True
    )
    assert (
        is_emoticon_img_attrs("https://example.com/photo.jpg", "STICKER-icon") is True
    )


def test_collect_blog_post_urls_raises_when_empty() -> None:
    class FakePage:
        async def goto(self, url: str, **kwargs: object) -> None:
            assert kwargs.get("wait_until") == "networkidle"

        async def content(self) -> str:
            return "<html><body><a href='/myid/category'>cat</a></body></html>"

    with pytest.raises(ValueError, match="no posts found at"):
        asyncio.run(
            collect_blog_post_urls(FakePage(), "https://blog.naver.com/myid", count=5)
        )


def test_scrape_post_calls_goto_with_networkidle() -> None:
    goto_kwargs: dict[str, object] = {}

    class FakePage:
        async def goto(self, url: str, **kwargs: object) -> None:
            goto_kwargs.update(kwargs)

        async def content(self) -> str:
            return NAVER_SMARTEDITOR_HTML

    doc = asyncio.run(scrape_post(FakePage(), "https://blog.naver.com/myid/223456789"))
    assert goto_kwargs.get("wait_until") == "networkidle"
    assert doc.title == "포포몬 첫 사용 후기"
