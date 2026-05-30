import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from naver_blog_bot.blog_scraper.login import run_login
from naver_blog_bot.config import Settings


def test_run_login_launches_headed_persistent_context(tmp_path: Path) -> None:
    settings = Settings(browser_profile_dir=tmp_path)
    page = MagicMock()
    page.goto = AsyncMock()
    ctx = MagicMock()
    ctx.new_page = AsyncMock(return_value=page)
    ctx.close = AsyncMock()
    launch_kwargs: dict = {}

    class _PW:
        def __init__(self) -> None:
            self.chromium = MagicMock()

            async def _launch(user_data_dir, **kw):
                launch_kwargs["user_data_dir"] = user_data_dir
                launch_kwargs.update(kw)
                return ctx

            self.chromium.launch_persistent_context = _launch

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    with patch("naver_blog_bot.blog_scraper.login.async_playwright", side_effect=_PW):
        asyncio.run(run_login(settings, wait_for_user=AsyncMock()))

    assert launch_kwargs["user_data_dir"] == str(tmp_path)
    assert launch_kwargs["headless"] is False
    page.goto.assert_awaited()
    ctx.close.assert_awaited_once()
