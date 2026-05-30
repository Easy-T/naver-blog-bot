from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from playwright.async_api import async_playwright

from naver_blog_bot.config import Settings

_LOGIN_URL = "https://nid.naver.com/nidlogin.login"


async def _default_wait_for_user() -> None:
    # Block on the user pressing Enter without blocking the event loop.
    await asyncio.get_event_loop().run_in_executor(
        None, input, "로그인을 완료한 뒤 이 터미널에서 Enter 를 누르세요... "
    )


async def run_login(
    settings: Settings,
    wait_for_user: Callable[[], Awaitable[None]] | None = None,
) -> None:
    waiter = wait_for_user or _default_wait_for_user
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            str(settings.browser_profile_dir),
            headless=False,
        )
        page = await context.new_page()
        try:
            await page.goto(_LOGIN_URL, wait_until="domcontentloaded")
            await waiter()
        finally:
            await context.close()
