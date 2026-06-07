from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from naver_blog_bot.blog_scraper.models import PostDocument, TextBlock
from naver_blog_bot.blog_scraper.service import scrape, scrape_blog, scrape_post
from naver_blog_bot.config import Settings


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(browser_profile_dir=tmp_path)


def _make_doc(url: str) -> PostDocument:
    return PostDocument(url=url, title="T", blocks=[TextBlock(content="x")])


def _make_playwright_patcher(context_factory):
    class _FakeBrowser:
        def __init__(self, ctx):
            self._ctx = ctx
            self.new_context = AsyncMock(return_value=ctx)

    class _FakeChromium:
        def __init__(self, ctx):
            self._ctx = ctx
            self.launch_persistent_context = AsyncMock(return_value=ctx)
            self.launch = AsyncMock(return_value=_FakeBrowser(ctx))

    class _FakePW:
        def __init__(self, ctx):
            self.chromium = _FakeChromium(ctx)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    def _async_playwright():
        return _FakePW(context_factory())

    return patch(
        "naver_blog_bot.blog_scraper.service.async_playwright",
        side_effect=_async_playwright,
    )


def _make_context(page: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.new_page = AsyncMock(return_value=page)
    ctx.close = AsyncMock()
    return ctx


def test_scrape_post_naver_routes_to_naver_adapter(tmp_path, monkeypatch):
    url = "https://m.blog.naver.com/testuser/123456"
    expected = _make_doc(url)
    page = MagicMock()
    ctx = _make_context(page)

    fake_scrape = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.scrape_post", fake_scrape
    )

    settings = _make_settings(tmp_path)

    with _make_playwright_patcher(lambda: ctx):
        result = asyncio.run(scrape_post(url, settings))

    fake_scrape.assert_awaited_once_with(page, url)
    ctx.close.assert_awaited_once()
    assert result == expected


def test_scrape_post_uses_browser_profile_dir(tmp_path, monkeypatch):
    url = "https://m.blog.naver.com/testuser/123456"
    page = MagicMock()
    ctx = _make_context(page)

    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.scrape_post",
        AsyncMock(return_value=_make_doc(url)),
    )

    settings = _make_settings(tmp_path)

    launched_with: list[str] = []

    class _CapturingPW:
        def __init__(self):
            self.chromium = MagicMock()

            async def _launch(user_data_dir, **kw):
                launched_with.append(user_data_dir)
                return ctx

            self.chromium.launch_persistent_context = _launch

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    with patch(
        "naver_blog_bot.blog_scraper.service.async_playwright",
        side_effect=_CapturingPW,
    ):
        asyncio.run(scrape_post(url, settings))

    assert launched_with == [str(tmp_path)]


def test_scrape_naver_post_url_returns_single_item(tmp_path, monkeypatch):
    url = "https://m.blog.naver.com/testuser/123456"
    expected = _make_doc(url)
    page = MagicMock()
    ctx = _make_context(page)

    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.scrape_post",
        AsyncMock(return_value=expected),
    )
    settings = _make_settings(tmp_path)

    with _make_playwright_patcher(lambda: ctx):
        result = scrape(url, count=5, settings=settings)

    assert result == [expected]


def test_scrape_blog_naver_collects_then_scrapes(tmp_path, monkeypatch):
    blog_url = "https://m.blog.naver.com/testuser"
    post_urls = [
        "https://m.blog.naver.com/testuser/1",
        "https://m.blog.naver.com/testuser/2",
    ]
    docs = [_make_doc(u) for u in post_urls]

    page = MagicMock()
    ctx = _make_context(page)

    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.collect_blog_post_urls",
        AsyncMock(return_value=post_urls),
    )
    scrape_mock = AsyncMock(side_effect=docs)
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.scrape_post", scrape_mock
    )

    sleep_calls: list[float] = []

    async def _fake_sleep(n: float) -> None:
        sleep_calls.append(n)

    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.asyncio.sleep", _fake_sleep
    )

    settings = _make_settings(tmp_path)

    with _make_playwright_patcher(lambda: ctx):
        result = asyncio.run(scrape_blog(blog_url, count=2, settings=settings))

    assert result == docs
    assert sleep_calls == [1]
    assert scrape_mock.await_count == 2
    ctx.close.assert_awaited_once()


def test_scrape_blog_naver_uses_single_context(tmp_path, monkeypatch):
    blog_url = "https://m.blog.naver.com/testuser"
    post_urls = ["https://m.blog.naver.com/testuser/1"]

    page = MagicMock()
    ctx = _make_context(page)

    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.collect_blog_post_urls",
        AsyncMock(return_value=post_urls),
    )
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.scrape_post",
        AsyncMock(return_value=_make_doc(post_urls[0])),
    )
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.asyncio.sleep", AsyncMock()
    )

    settings = _make_settings(tmp_path)

    launch_count = 0

    class _CountingPW:
        def __init__(self):
            nonlocal launch_count
            self.chromium = MagicMock()

            async def _launch(user_data_dir, **kw):
                nonlocal launch_count
                launch_count += 1
                return ctx

            self.chromium.launch_persistent_context = _launch

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    with patch(
        "naver_blog_bot.blog_scraper.service.async_playwright",
        side_effect=_CountingPW,
    ):
        asyncio.run(scrape_blog(blog_url, count=1, settings=settings))

    assert launch_count == 1


def test_scrape_blog_tistory_routes_to_tistory_adapter(tmp_path, monkeypatch):
    blog_url = "https://someuser.tistory.com"
    post_urls = [
        "https://someuser.tistory.com/1",
        "https://someuser.tistory.com/2",
    ]
    docs = [_make_doc(u) for u in post_urls]

    page = MagicMock()
    ctx = _make_context(page)

    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.tistory.collect_blog_post_urls",
        AsyncMock(return_value=post_urls),
    )
    scrape_mock = AsyncMock(side_effect=docs)
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.tistory.scrape_post", scrape_mock
    )

    sleep_calls: list[float] = []

    async def _fake_sleep(n: float) -> None:
        sleep_calls.append(n)

    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.asyncio.sleep", _fake_sleep
    )

    settings = _make_settings(tmp_path)

    with _make_playwright_patcher(lambda: ctx):
        result = asyncio.run(scrape_blog(blog_url, count=2, settings=settings))

    assert result == docs
    assert scrape_mock.await_count == 2
    assert sleep_calls == [1]


def test_scrape_blog_generic_uses_generic_scraper_no_collector(tmp_path, monkeypatch):
    url = "https://example.com/my-blog"
    expected = _make_doc(url)

    page = MagicMock()
    ctx = _make_context(page)

    generic_mock = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.generic.scrape_post", generic_mock
    )

    naver_collect_mock = AsyncMock()
    tistory_collect_mock = AsyncMock()
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.collect_blog_post_urls",
        naver_collect_mock,
    )
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.tistory.collect_blog_post_urls",
        tistory_collect_mock,
    )

    settings = _make_settings(tmp_path)

    with _make_playwright_patcher(lambda: ctx):
        result = asyncio.run(scrape_blog(url, count=5, settings=settings))

    assert result == [expected]
    generic_mock.assert_awaited_once_with(page, url)
    ctx.close.assert_awaited_once()
    naver_collect_mock.assert_not_awaited()
    tistory_collect_mock.assert_not_awaited()


def test_scrape_naver_blog_url_routes_to_scrape_blog(tmp_path, monkeypatch):
    blog_url = "https://m.blog.naver.com/testuser"
    post_urls = ["https://m.blog.naver.com/testuser/1"]
    docs = [_make_doc(u) for u in post_urls]

    page = MagicMock()
    ctx = _make_context(page)

    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.collect_blog_post_urls",
        AsyncMock(return_value=post_urls),
    )
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.scrape_post",
        AsyncMock(side_effect=docs),
    )
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.asyncio.sleep", AsyncMock()
    )

    settings = _make_settings(tmp_path)

    with _make_playwright_patcher(lambda: ctx):
        result = scrape(blog_url, count=1, settings=settings)

    assert result == docs


def test_scrape_blog_no_sleep_for_single_post(tmp_path, monkeypatch):
    blog_url = "https://m.blog.naver.com/testuser"
    post_urls = ["https://m.blog.naver.com/testuser/1"]

    page = MagicMock()
    ctx = _make_context(page)

    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.collect_blog_post_urls",
        AsyncMock(return_value=post_urls),
    )
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.scrape_post",
        AsyncMock(return_value=_make_doc(post_urls[0])),
    )

    sleep_calls: list[float] = []

    async def _fake_sleep(n: float) -> None:
        sleep_calls.append(n)

    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.asyncio.sleep", _fake_sleep
    )

    settings = _make_settings(tmp_path)

    with _make_playwright_patcher(lambda: ctx):
        asyncio.run(scrape_blog(blog_url, count=1, settings=settings))

    assert sleep_calls == []


def test_scrape_blog_all_collects_all_then_scrapes(tmp_path, monkeypatch):
    from naver_blog_bot.blog_scraper.service import scrape_blog_all

    blog_url = "https://m.blog.naver.com/flowerbend"
    post_urls = [
        "https://m.blog.naver.com/flowerbend/1",
        "https://m.blog.naver.com/flowerbend/2",
    ]
    docs = [_make_doc(u) for u in post_urls]

    page = MagicMock()
    ctx = _make_context(page)

    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.collect_all_post_urls",
        AsyncMock(return_value=post_urls),
    )
    scrape_mock = AsyncMock(side_effect=docs)
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.scrape_post", scrape_mock
    )
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.asyncio.sleep", AsyncMock()
    )

    settings = _make_settings(tmp_path)

    with _make_playwright_patcher(lambda: ctx):
        result = asyncio.run(scrape_blog_all(blog_url, settings=settings))

    assert result == docs
    assert scrape_mock.await_count == 2
    ctx.close.assert_awaited_once()


def test_scrape_all_sync_wrapper_runs_async(tmp_path, monkeypatch):
    from naver_blog_bot.blog_scraper.service import scrape_all

    blog_url = "https://m.blog.naver.com/flowerbend"
    post_urls = ["https://m.blog.naver.com/flowerbend/1"]
    docs = [_make_doc(post_urls[0])]

    page = MagicMock()
    ctx = _make_context(page)

    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.collect_all_post_urls",
        AsyncMock(return_value=post_urls),
    )
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.naver.scrape_post",
        AsyncMock(return_value=docs[0]),
    )
    monkeypatch.setattr(
        "naver_blog_bot.blog_scraper.service.asyncio.sleep", AsyncMock()
    )

    settings = _make_settings(tmp_path)
    with _make_playwright_patcher(lambda: ctx):
        result = scrape_all(blog_url, settings=settings)
    assert result == docs
