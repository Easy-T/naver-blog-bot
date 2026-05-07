import asyncio

import pytest

from naver_blog_bot.blog_scraper.adapters.generic import (
    parse_post_html,
    scrape_post,
)
from naver_blog_bot.blog_scraper.models import EmoticonBlock, ImageBlock, TextBlock


NESTED_BLOCK_HTML = """
<html>
<head><title>중첩 블록</title></head>
<body>
  <article>
    <div><p>첫 문단</p><img alt="사진"><p>둘째 문단</p></div>
  </article>
</body>
</html>
"""

ARTICLE_HTML = """
<html>
<head><title>리뷰 글</title></head>
<body>
  <article>
    <p>이 제품을 써봤습니다.</p>
    <img src="https://example.com/product.jpg" alt="제품 이미지">
    <p>총평은 매우 만족입니다.</p>
  </article>
</body>
</html>
"""

CONTENT_CLASS_HTML = """
<html>
<head><title>블로그 포스트</title></head>
<body>
  <div class="content">
    <p>본문 내용입니다.</p>
    <img src="https://example.com/image.jpg" alt="본문 이미지">
    <p>마지막 문장.</p>
  </div>
</body>
</html>
"""

CONTENT_ID_HTML = """
<html>
<head><title>일반 글</title></head>
<body>
  <div id="content">
    <p>아이디 셀렉터 본문.</p>
    <img src="https://example.com/id.jpg" alt="아이디 이미지">
  </div>
</body>
</html>
"""


def test_parse_article_blocks_in_order() -> None:
    doc = parse_post_html(ARTICLE_HTML, "https://example.com/post/1")

    assert doc.title == "리뷰 글"
    assert [type(b) for b in doc.blocks] == [TextBlock, ImageBlock, TextBlock]
    assert doc.blocks[0].content == "이 제품을 써봤습니다."
    assert doc.blocks[1].alt == "제품 이미지"
    assert doc.blocks[2].content == "총평은 매우 만족입니다."


def test_parse_article_no_emoticon_blocks() -> None:
    doc = parse_post_html(ARTICLE_HTML, "https://example.com/post/1")

    for block in doc.blocks:
        assert not isinstance(block, EmoticonBlock)


def test_parse_fallback_to_content_class() -> None:
    doc = parse_post_html(CONTENT_CLASS_HTML, "https://example.com/post/2")

    assert doc.title == "블로그 포스트"
    assert [type(b) for b in doc.blocks] == [TextBlock, ImageBlock, TextBlock]
    assert doc.blocks[0].content == "본문 내용입니다."
    assert doc.blocks[1].alt == "본문 이미지"


def test_parse_fallback_to_content_id() -> None:
    doc = parse_post_html(CONTENT_ID_HTML, "https://example.com/post/3")

    assert [type(b) for b in doc.blocks] == [TextBlock, ImageBlock]
    assert doc.blocks[0].content == "아이디 셀렉터 본문."
    assert doc.blocks[1].alt == "아이디 이미지"


def test_parse_unsupported_structure_raises() -> None:
    html = "<!-- no html element at all -->"
    with pytest.raises(ValueError, match="unsupported generic post structure"):
        parse_post_html(html, "https://example.com/post/99")


def test_scrape_post_uses_networkidle() -> None:
    goto_calls: list[tuple[str, dict[str, object]]] = []

    class FakePage:
        async def goto(self, url: str, **kwargs: object) -> None:
            goto_calls.append((url, dict(kwargs)))

        async def content(self) -> str:
            return ARTICLE_HTML

    doc = asyncio.run(scrape_post(FakePage(), "https://example.com/post/1"))
    assert len(goto_calls) == 1
    assert goto_calls[0][0] == "https://example.com/post/1"
    assert goto_calls[0][1].get("wait_until") == "networkidle"
    assert doc.title == "리뷰 글"


def test_parse_nested_block_preserves_order() -> None:
    doc = parse_post_html(NESTED_BLOCK_HTML, "https://example.com/post/5")

    assert [type(b) for b in doc.blocks] == [TextBlock, ImageBlock, TextBlock]
    assert doc.blocks[0].content == "첫 문단"
    assert doc.blocks[1].alt == "사진"
    assert doc.blocks[2].content == "둘째 문단"
