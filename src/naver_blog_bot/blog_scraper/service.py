from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from naver_blog_bot.blog_scraper.adapters import generic, naver, tistory
from naver_blog_bot.blog_scraper.models import PostDocument
from naver_blog_bot.config import Settings


def _is_naver(hostname: str) -> bool:
    return hostname in ("blog.naver.com", "m.blog.naver.com")


def _is_tistory(hostname: str) -> bool:
    return hostname.endswith(".tistory.com")


async def _make_context(pw, *, naver_persistent: bool, settings: Settings):
    if naver_persistent:
        return await pw.chromium.launch_persistent_context(
            str(settings.browser_profile_dir),
            headless=True,
        )
    browser = await pw.chromium.launch(headless=True)
    return await browser.new_context()


async def scrape_post(url: str, settings: Settings) -> PostDocument:
    hostname = urlparse(url).hostname or ""
    is_naver = _is_naver(hostname)
    async with async_playwright() as pw:
        context = await _make_context(pw, naver_persistent=is_naver, settings=settings)
        page = await context.new_page()
        try:
            if is_naver:
                doc = await naver.scrape_post(page, url)
            elif _is_tistory(hostname):
                doc = await tistory.scrape_post(page, url)
            else:
                doc = await generic.scrape_post(page, url)
        finally:
            await context.close()
    return doc


async def scrape_blog(url: str, count: int, settings: Settings) -> list[PostDocument]:
    hostname = urlparse(url).hostname or ""
    is_naver = _is_naver(hostname)

    async with async_playwright() as pw:
        context = await _make_context(pw, naver_persistent=is_naver, settings=settings)
        page = await context.new_page()
        try:
            if is_naver:
                post_urls = await naver.collect_blog_post_urls(page, url, count)
                scrape_fn = naver.scrape_post
            elif _is_tistory(hostname):
                post_urls = await tistory.collect_blog_post_urls(page, url, count)
                scrape_fn = tistory.scrape_post
            else:
                doc = await generic.scrape_post(page, url)
                return [doc]

            results: list[PostDocument] = []
            for i, post_url in enumerate(post_urls):
                if i > 0:
                    await asyncio.sleep(1)
                doc = await scrape_fn(page, post_url)
                results.append(doc)
        finally:
            await context.close()

    return results


def scrape(url: str, count: int, settings: Settings) -> list[PostDocument]:
    hostname = urlparse(url).hostname or ""

    if _is_naver(hostname):
        is_blog = naver.is_blog_url(url)
    elif _is_tistory(hostname):
        is_blog = tistory.is_blog_url(url)
    else:
        is_blog = False

    if is_blog:
        return asyncio.run(scrape_blog(url, count, settings))
    else:
        doc = asyncio.run(scrape_post(url, settings))
        return [doc]
