import asyncio

import pytest

from naver_blog_bot.blog_scraper.adapters.tistory import (
    collect_blog_post_urls,
    collect_post_urls,
    is_blog_url,
    parse_post_html,
    scrape_post,
)
from naver_blog_bot.blog_scraper.models import EmoticonBlock, ImageBlock, TextBlock


ENTRY_CONTENT_HTML = """
<html>
<head><title>맛집 방문기</title></head>
<body>
  <article class="entry-content">
    <p>오늘 방문한 맛집입니다.</p>
    <img src="https://example.tistory.com/photo1.jpg" alt="입구 사진">
    <p>음식이 정말 맛있었어요!</p>
  </article>
</body>
</html>
"""

ARTICLE_VIEW_HTML = """
<html>
<head><title>여행 후기</title></head>
<body>
  <div class="article_view">
    <p>여행을 다녀왔어요.</p>
    <img src="https://example.tistory.com/travel.jpg" alt="여행 사진">
    <p>정말 좋았습니다.</p>
  </div>
</body>
</html>
"""

CONTENT_ID_HTML = """
<html>
<head><title>일상 글</title></head>
<body>
  <div id="content">
    <p>오늘 일상입니다.</p>
    <img src="https://example.tistory.com/daily.jpg" alt="일상 사진">
  </div>
</body>
</html>
"""

POST_LIST_HTML = """
<html><body>
  <a href="/123">첫 번째 글</a>
  <a href="https://myblog.tistory.com/456">두 번째 글</a>
  <a href="/789">세 번째 글</a>
  <a href="/category/food">음식 카테고리</a>
  <a href="https://myblog.tistory.com/456">두 번째 글 (중복)</a>
</body></html>
"""


def test_is_blog_url_returns_true_for_index() -> None:
    assert is_blog_url("https://myblog.tistory.com") is True
    assert is_blog_url("https://myblog.tistory.com/category/food") is True


def test_is_blog_url_returns_false_for_post() -> None:
    assert is_blog_url("https://myblog.tistory.com/123") is False
    assert is_blog_url("https://myblog.tistory.com/456") is False


def test_parse_entry_content_blocks_in_order() -> None:
    doc = parse_post_html(ENTRY_CONTENT_HTML, "https://myblog.tistory.com/1")

    assert doc.title == "맛집 방문기"
    assert [type(b) for b in doc.blocks] == [TextBlock, ImageBlock, TextBlock]
    assert doc.blocks[0].content == "오늘 방문한 맛집입니다."
    assert doc.blocks[1].alt == "입구 사진"
    assert doc.blocks[2].content == "음식이 정말 맛있었어요!"


def test_parse_entry_content_no_emoticon_blocks() -> None:
    doc = parse_post_html(ENTRY_CONTENT_HTML, "https://myblog.tistory.com/1")

    for block in doc.blocks:
        assert not isinstance(block, EmoticonBlock)


def test_parse_fallback_to_article_view() -> None:
    doc = parse_post_html(ARTICLE_VIEW_HTML, "https://myblog.tistory.com/2")

    assert doc.title == "여행 후기"
    assert [type(b) for b in doc.blocks] == [TextBlock, ImageBlock, TextBlock]
    assert doc.blocks[0].content == "여행을 다녀왔어요."


def test_parse_fallback_to_content_id() -> None:
    doc = parse_post_html(CONTENT_ID_HTML, "https://myblog.tistory.com/3")

    assert [type(b) for b in doc.blocks] == [TextBlock, ImageBlock]
    assert doc.blocks[0].content == "오늘 일상입니다."
    assert doc.blocks[1].alt == "일상 사진"


def test_parse_unsupported_structure_raises() -> None:
    html = "<html><body><div>아무 구조도 없음</div></body></html>"
    with pytest.raises(ValueError, match="unsupported Tistory post structure"):
        parse_post_html(html, "https://myblog.tistory.com/99")


def test_collect_post_urls_filters_and_deduplicates() -> None:
    urls = collect_post_urls(
        POST_LIST_HTML,
        "https://myblog.tistory.com",
        count=10,
    )

    assert "https://myblog.tistory.com/123" in urls
    assert "https://myblog.tistory.com/456" in urls
    assert "https://myblog.tistory.com/789" in urls
    assert not any("category" in u for u in urls)
    assert len(urls) == len(set(urls))


def test_collect_post_urls_relative_links() -> None:
    html = "<html><body><a href='/100'>글</a><a href='/200'>글2</a></body></html>"
    urls = collect_post_urls(html, "https://myblog.tistory.com", count=5)
    assert "https://myblog.tistory.com/100" in urls
    assert "https://myblog.tistory.com/200" in urls


def test_collect_post_urls_honors_count() -> None:
    urls = collect_post_urls(
        POST_LIST_HTML,
        "https://myblog.tistory.com",
        count=2,
    )

    assert len(urls) <= 2


def test_scrape_post_uses_networkidle() -> None:
    goto_calls: list[tuple[str, dict[str, object]]] = []

    class FakePage:
        async def goto(self, url: str, **kwargs: object) -> None:
            goto_calls.append((url, dict(kwargs)))

        async def content(self) -> str:
            return ENTRY_CONTENT_HTML

    doc = asyncio.run(scrape_post(FakePage(), "https://myblog.tistory.com/1"))
    assert len(goto_calls) == 1
    assert goto_calls[0][0] == "https://myblog.tistory.com/1"
    assert goto_calls[0][1].get("wait_until") == "networkidle"
    assert doc.title == "맛집 방문기"


def test_collect_blog_post_urls_raises_when_empty() -> None:
    goto_kwargs: dict[str, object] = {}

    class FakePage:
        async def goto(self, url: str, **kwargs: object) -> None:
            goto_kwargs.update(kwargs)

        async def content(self) -> str:
            return "<html><body><a href='/category/food'>카테고리</a></body></html>"

    with pytest.raises(ValueError, match="no posts found at"):
        asyncio.run(
            collect_blog_post_urls(FakePage(), "https://myblog.tistory.com", count=5)
        )
    assert goto_kwargs.get("wait_until") == "networkidle"
