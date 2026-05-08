from __future__ import annotations

from naver_blog_bot.blog_scraper.adapters.html import (
    HtmlNode,
    first_title,
    normalize_text,
    parse_html,
    select_all,
    select_first,
)
from naver_blog_bot.blog_scraper.models import (
    ImageBlock,
    PostBlock,
    PostDocument,
    TextBlock,
)

_CONTENT_SELECTORS = [
    "article",
    "main",
    ".content",
    "#content",
    "body",
]

_BLOCK_ELEMENTS = frozenset(
    {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre"}
)


def _walk_content(node: HtmlNode, blocks: list[PostBlock], seen_imgs: set[int]) -> None:
    for child in node.children:
        if isinstance(child, str):
            text = normalize_text(child)
            if text:
                blocks.append(TextBlock(content=text))
        elif child.tag == "img":
            node_id = id(child)
            if node_id not in seen_imgs:
                seen_imgs.add(node_id)
                blocks.append(ImageBlock(alt=child.attrs.get("alt", "")))
        elif child.tag in _BLOCK_ELEMENTS:
            has_block_child = any(
                isinstance(c, HtmlNode) and c.tag in _BLOCK_ELEMENTS
                for c in child.children
            )
            if has_block_child:
                _walk_content(child, blocks, seen_imgs)
            else:
                text = normalize_text(child.text_content())
                if text:
                    blocks.append(TextBlock(content=text))
                for img in select_all(child, "img"):
                    node_id = id(img)
                    if node_id not in seen_imgs:
                        seen_imgs.add(node_id)
                        blocks.append(ImageBlock(alt=img.attrs.get("alt", "")))
        else:
            _walk_content(child, blocks, seen_imgs)


def parse_post_html(html: str, url: str) -> PostDocument:
    root = parse_html(html)
    title = first_title(root)

    content = select_first(root, _CONTENT_SELECTORS)
    if content is None:
        raise ValueError("unsupported generic post structure")

    blocks: list[PostBlock] = []
    seen_imgs: set[int] = set()
    _walk_content(content, blocks, seen_imgs)

    return PostDocument(url=url, title=title, blocks=blocks)


async def scrape_post(page: object, url: str) -> PostDocument:
    await page.goto(url, wait_until="networkidle")  # type: ignore[attr-defined]
    html: str = await page.content()  # type: ignore[attr-defined]
    return parse_post_html(html, url)


async def collect_blog_post_urls(page: object, url: str, count: int) -> list[str]:
    # Generic sites have no known listing structure; treat the URL itself as the only post.
    return [url]
