from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

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

_POST_PATH_RE = re.compile(r"/\d+$")

_CONTENT_SELECTORS = [
    "article.entry-content",
    ".tt_article_useless_p_margin",
    ".article_view",
    "#content",
]

_BLOCK_ELEMENTS = frozenset(
    {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre"}
)


def is_blog_url(url: str) -> bool:
    path = urlparse(url).path.rstrip("/")
    segments = [s for s in path.split("/") if s]
    if segments and segments[-1].isdigit():
        return False
    return True


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
        raise ValueError("unsupported Tistory post structure")

    blocks: list[PostBlock] = []
    seen_imgs: set[int] = set()
    _walk_content(content, blocks, seen_imgs)

    return PostDocument(url=url, title=title, blocks=blocks)


def collect_post_urls(html: str, base_url: str, count: int) -> list[str]:
    root = parse_html(html)
    seen: set[str] = set()
    result: list[str] = []

    for a in select_all(root, "a"):
        if len(result) >= count:
            break
        href = a.attrs.get("href", "").strip()
        if not href:
            continue
        absolute = urljoin(base_url, href)
        path = urlparse(absolute).path.rstrip("/")
        if not _POST_PATH_RE.search(path):
            continue
        if absolute not in seen:
            seen.add(absolute)
            result.append(absolute)

    return result


async def scrape_post(page: object, url: str) -> PostDocument:
    await page.goto(url, wait_until="networkidle")  # type: ignore[attr-defined]
    html: str = await page.content()  # type: ignore[attr-defined]
    return parse_post_html(html, url)


async def collect_blog_post_urls(page: object, url: str, count: int) -> list[str]:
    await page.goto(url, wait_until="networkidle")  # type: ignore[attr-defined]
    html: str = await page.content()  # type: ignore[attr-defined]
    urls = collect_post_urls(html, url, count)
    if not urls:
        raise ValueError(f"no posts found at {url}")
    return urls
