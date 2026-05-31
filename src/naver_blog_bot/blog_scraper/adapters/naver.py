from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from naver_blog_bot.blog_scraper.adapters.html import (
    HtmlNode,
    element_children,
    first_title,
    normalize_text,
    parse_html,
    select_all,
    select_first,
)
from naver_blog_bot.blog_scraper.models import (
    EmoticonBlock,
    ImageBlock,
    PostBlock,
    PostDocument,
    TextBlock,
)

_PC_HOST = "blog.naver.com"
_MOBILE_HOST = "m.blog.naver.com"


def normalize_naver_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname == _PC_HOST:
        parsed = parsed._replace(netloc=_MOBILE_HOST)
    return urlunparse(parsed)


def is_blog_url(url: str) -> bool:
    parsed = urlparse(normalize_naver_url(url))
    path = parsed.path.rstrip("/")
    if "PostView.naver" in path:
        return False
    segments = [s for s in path.split("/") if s]
    if len(segments) >= 2 and segments[-1].isdigit():
        return False
    return True


def post_list_url(url: str) -> str:
    parsed = urlparse(normalize_naver_url(url))
    path = parsed.path.rstrip("/")
    segments = [s for s in path.split("/") if s]
    blog_id = segments[0] if segments else ""
    existing = parse_qs(parsed.query)
    query: dict[str, object] = {}
    category = existing.get("categoryNo")
    if category and category[0]:
        query["categoryNo"] = category[0]
    result = parsed._replace(path=f"/{blog_id}", query=urlencode(query), fragment="")
    return urlunparse(result)


_EMOTICON_URL_PATTERNS = [
    "ogq.me",
    "/ogq/",
    "pstatic.net/static/se/sticker",
    "pstatic.net/static/se/emoticon",
    "static/se/sticker",
    "static/se/emoticon",
]

_EMOTICON_CLASS_KEYWORDS = ["emoticon", "sticker"]


def is_emoticon_img_attrs(src: str, classes: str) -> bool:
    src_lower = src.lower()
    classes_lower = classes.lower()
    for pattern in _EMOTICON_URL_PATTERNS:
        if pattern in src_lower:
            return True
    for keyword in _EMOTICON_CLASS_KEYWORDS:
        if keyword in classes_lower:
            return True
    return False


def _img_block_from_node(img: HtmlNode) -> ImageBlock | EmoticonBlock:
    src = img.attrs.get("src", "")
    alt = img.attrs.get("alt", "")
    classes = img.attrs.get("class", "")
    if is_emoticon_img_attrs(src, classes):
        return EmoticonBlock(description=alt)
    return ImageBlock(alt=alt)


def _classify_se_component(component: HtmlNode) -> list[PostBlock]:
    classes = component.class_names()

    if "se-sticker" in classes:
        imgs = select_all(component, "img")
        if imgs:
            img = imgs[0]
            alt = img.attrs.get("alt", "")
            return [EmoticonBlock(description=alt)]
        return []

    if "se-text" in classes:
        text = normalize_text(component.text_content())
        if text:
            return [TextBlock(content=text)]
        return []

    if "se-image" in classes:
        blocks: list[PostBlock] = []
        for img in select_all(component, "img"):
            blocks.append(_img_block_from_node(img))
        return blocks

    blocks = []
    text = normalize_text(component.text_content())
    if text:
        blocks.append(TextBlock(content=text))
    for img in select_all(component, "img"):
        blocks.append(_img_block_from_node(img))
    return blocks


def _parse_se_main_container(container: HtmlNode) -> list[PostBlock]:
    blocks: list[PostBlock] = []
    for child in element_children(container):
        if "se-component" in child.class_names():
            blocks.extend(_classify_se_component(child))
    return blocks


def _parse_legacy_area(area: HtmlNode) -> list[PostBlock]:
    blocks: list[PostBlock] = []

    def _walk(node: HtmlNode) -> None:
        for child in node.children:
            if isinstance(child, str):
                text = normalize_text(child)
                if text:
                    blocks.append(TextBlock(content=text))
            elif isinstance(child, HtmlNode):
                if child.tag == "img":
                    blocks.append(_img_block_from_node(child))
                elif child.tag in ("p", "div", "span", "br"):
                    text = normalize_text(child.text_content())
                    if text:
                        blocks.append(TextBlock(content=text))
                    for img in select_all(child, "img"):
                        blocks.append(_img_block_from_node(img))
                else:
                    _walk(child)

    _walk(area)
    return blocks


def parse_post_html(html: str, url: str) -> PostDocument:
    root = parse_html(html)
    title = first_title(root)

    containers = select_all(root, ".se-main-container")
    if containers:
        blocks = _parse_se_main_container(containers[0])
    else:
        area = select_first(root, ["#postViewArea"])
        if area is not None:
            blocks = _parse_legacy_area(area)
        else:
            raise ValueError("unsupported Naver post structure")

    return PostDocument(url=url, title=title, blocks=blocks)


_POST_PATH_RE = re.compile(r"^/([^/]+)/(\d+)$")


def _resolve_post_url(href: str, base_url: str) -> str | None:
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)

    if parsed.hostname == _PC_HOST:
        absolute = normalize_naver_url(absolute)
        parsed = urlparse(absolute)

    if parsed.hostname == _MOBILE_HOST:
        path = parsed.path.rstrip("/")
        m = _POST_PATH_RE.match(path)
        if m:
            return absolute.rstrip("/")
        if "PostView.naver" in path:
            qs = parse_qs(parsed.query)
            blog_id_list = qs.get("blogId", [])
            log_no_list = qs.get("logNo", [])
            if blog_id_list and log_no_list:
                return f"https://{_MOBILE_HOST}/{blog_id_list[0]}/{log_no_list[0]}"
        return None

    return None


def _select_post_hrefs(hrefs: list[str], base_url: str, count: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for href in hrefs:
        if len(result) >= count:
            break
        cleaned = (href or "").strip()
        if not cleaned:
            continue
        resolved = _resolve_post_url(cleaned, base_url)
        if resolved and resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def category_list_api_url(url: str) -> str | None:
    parsed = urlparse(normalize_naver_url(url))
    segments = [s for s in parsed.path.split("/") if s]
    blog_id = segments[0] if segments else ""
    category = parse_qs(parsed.query).get("categoryNo")
    if not (category and category[0]):
        return None
    query = urlencode(
        {
            "blogId": blog_id,
            "categoryNo": category[0],
            "countPerPage": 30,
            "currentPage": 1,
        }
    )
    return f"https://{_PC_HOST}/PostTitleListAsync.naver?{query}"


def _select_post_urls_from_titlelist(
    payload: dict, blog_id: str, count: int
) -> list[str]:
    posts = payload.get("postList") or []
    result: list[str] = []
    for post in posts:
        if len(result) >= count:
            break
        log_no = post.get("logNo")
        if log_no:
            result.append(f"https://{_MOBILE_HOST}/{blog_id}/{log_no}")
    return result


async def scrape_post(page: object, url: str) -> PostDocument:
    mobile_url = normalize_naver_url(url)
    await page.goto(mobile_url, wait_until="networkidle")  # type: ignore[attr-defined]
    html: str = await page.content()  # type: ignore[attr-defined]
    return parse_post_html(html, mobile_url)


async def collect_blog_post_urls(page: object, url: str, count: int) -> list[str]:
    api_url = category_list_api_url(url)
    if api_url is not None:
        return await _collect_category_post_urls(page, url, api_url, count)
    list_url = post_list_url(url)
    await page.goto(list_url, wait_until="networkidle")  # type: ignore[attr-defined]
    urls: list[str] = []
    for _ in range(5):
        hrefs: list[str] = await page.eval_on_selector_all(  # type: ignore[attr-defined]
            "a", "els => els.map(e => e.href).filter(Boolean)"
        )
        urls = _select_post_hrefs(hrefs, list_url, count)
        if urls:
            break
        await page.wait_for_timeout(1000)  # type: ignore[attr-defined]
    if not urls:
        raise ValueError(f"no posts found at {url}")
    return urls


_LOGNO_RE = re.compile(r'"logNo"\s*:\s*"?(\d{6,})"?')


def _parse_naver_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith(")]}'"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[4:]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Naver's response embeds raw HTML (e.g. pagingHtml with \' escapes)
        # that is not valid JSON. Fall back to extracting logNo values directly,
        # preserving order. That is all collect_blog_post_urls needs.
        log_nos = list(dict.fromkeys(_LOGNO_RE.findall(cleaned)))
        if log_nos:
            return {"postList": [{"logNo": ln} for ln in log_nos]}
        raise ValueError("Naver category API returned invalid JSON") from None


async def _collect_category_post_urls(
    page: object, url: str, api_url: str, count: int
) -> list[str]:
    parsed = urlparse(normalize_naver_url(url))
    segments = [s for s in parsed.path.split("/") if s]
    blog_id = segments[0] if segments else ""
    # Establish same-origin cookies before fetching the JSON API.
    await page.goto(  # type: ignore[attr-defined]
        f"https://{_PC_HOST}/{blog_id}", wait_until="networkidle"
    )
    raw: str = await page.evaluate(  # type: ignore[attr-defined]
        """async (apiUrl) => {
            const r = await fetch(apiUrl, {headers: {'Accept': 'application/json'}, credentials: 'include'});
            return await r.text();
        }""",
        api_url,
    )
    data = _parse_naver_json(raw)
    urls = _select_post_urls_from_titlelist(data, blog_id, count)
    if not urls:
        raise ValueError(f"no posts found at {url}")
    return urls
