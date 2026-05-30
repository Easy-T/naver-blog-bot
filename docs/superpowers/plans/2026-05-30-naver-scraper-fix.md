**Status:** completed
**RPI-Cycle:** 7
**Started:** 2026-05-30

# Naver Scraper Post-URL Collection Fix + Category Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 실제 네이버 블로그 URL에서 포스트 목록 수집이 동작하도록 (1) live DOM 기반화(Task 1·2, 완료), (2) 레거시 PostList.naver → 모바일 블로그 홈 엔드포인트로 수정 + 렌더 폴링(Task 4), (3) `naver-bot login` headed 세션 추가(Task 5), 카테고리별 프로필 학습을 지원한다.

**Architecture:** `blog_scraper/adapters/naver.py` 내부만 변경. URL 추출 로직을 순수 함수 `_select_post_hrefs`로 분리해 오프라인 테스트를 유지하고, `collect_blog_post_urls`는 `page.eval_on_selector_all`로 live DOM 앵커를 읽는다. 본문 파서와 `service.py`/`cli.py` 시그니처는 불변.

**Tech Stack:** Python 3.11+, Playwright(async), pytest, ruff.

---

## File Structure

**수정 파일:**
- `src/naver_blog_bot/blog_scraper/adapters/naver.py`
  - 신규: `_select_post_hrefs(hrefs, base_url, count)` 순수 함수
  - 변경: `post_list_url(url)` — `categoryNo` 보존
  - 변경: `collect_blog_post_urls(page, url, count)` — live DOM 추출
  - 제거: `collect_post_urls(html, base_url, count)` (정적 HTML 파싱; production 미사용화)
- `tests/unit/test_blog_scraper_naver.py`
  - 제거: import 라인의 `collect_post_urls` 심볼
  - 제거: `test_collect_post_urls_from_mobile_post_list`, `test_collect_post_urls_canonicalizes_relative_post_view_link`, `test_collect_post_urls_canonicalizes_pc_absolute_link` (실제 존재하는 3개)
  - 신규: `_select_post_hrefs` 테스트 2개, `post_list_url` 카테고리 테스트 2개, `is_blog_url` 카테고리 테스트 1개
  - 변경: `test_collect_blog_post_urls_raises_when_empty` → live DOM fake page 기반으로 교체 + 정상 수집 테스트 추가

---

## Task 1: 순수 함수 분리 + 카테고리 지원

**Files:**
- Modify: `src/naver_blog_bot/blog_scraper/adapters/naver.py`
- Test: `tests/unit/test_blog_scraper_naver.py`

- [x] **Step 1: 실패 테스트 추가**

`tests/unit/test_blog_scraper_naver.py`에 추가:

```python
def test_select_post_hrefs_extracts_unique_posts() -> None:
    hrefs = [
        "https://m.blog.naver.com/foo/100",
        "https://m.blog.naver.com/foo/100",
        "https://m.blog.naver.com/foo/200",
        "https://example.com/other",
        "",
    ]
    urls = naver._select_post_hrefs(hrefs, "https://m.blog.naver.com/foo", 5)
    assert urls == [
        "https://m.blog.naver.com/foo/100",
        "https://m.blog.naver.com/foo/200",
    ]


def test_select_post_hrefs_respects_count() -> None:
    hrefs = [
        "https://m.blog.naver.com/foo/1",
        "https://m.blog.naver.com/foo/2",
        "https://m.blog.naver.com/foo/3",
    ]
    urls = naver._select_post_hrefs(hrefs, "https://m.blog.naver.com/foo", 2)
    assert urls == [
        "https://m.blog.naver.com/foo/1",
        "https://m.blog.naver.com/foo/2",
    ]


def test_post_list_url_preserves_category_no() -> None:
    url = naver.post_list_url("https://blog.naver.com/foo?categoryNo=7")
    assert "blogId=foo" in url
    assert "categoryNo=7" in url


def test_post_list_url_without_category_has_no_category_param() -> None:
    url = naver.post_list_url("https://blog.naver.com/foo")
    assert "categoryNo" not in url


def test_is_blog_url_detects_category_home() -> None:
    assert naver.is_blog_url("https://blog.naver.com/foo?categoryNo=7") is True
```

- [x] **Step 2: 실패 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_blog_scraper_naver.py -k "select_post_hrefs or category" -v 2>&1 | tail -20
```

Expected: FAIL (`_select_post_hrefs` 없음, categoryNo 미보존)

- [x] **Step 3: `_select_post_hrefs` 추가**

`src/naver_blog_bot/blog_scraper/adapters/naver.py`에서 `collect_post_urls` 함수 바로 위에 추가:

```python
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
```

- [x] **Step 4: `post_list_url` 카테고리 보존**

`post_list_url`을 아래로 교체:

```python
def post_list_url(url: str) -> str:
    parsed = urlparse(normalize_naver_url(url))
    path = parsed.path.rstrip("/")
    segments = [s for s in path.split("/") if s]
    blog_id = segments[0] if segments else ""
    existing = parse_qs(parsed.query)
    query: dict[str, object] = {"blogId": blog_id, "currentPage": 1}
    category = existing.get("categoryNo")
    if category and category[0]:
        query["categoryNo"] = category[0]
    result = parsed._replace(path="/PostList.naver", query=urlencode(query), fragment="")
    return urlunparse(result)
```

(`parse_qs`는 이미 import되어 있음 — line 4 확인. 없으면 `from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse`로 보강.)

- [x] **Step 5: 통과 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_blog_scraper_naver.py -k "select_post_hrefs or category" -v
```

Expected: PASS

- [x] **Step 6: 커밋**

```bash
cd /home/indietogo/projects/naver-blog-bot && git add src/naver_blog_bot/blog_scraper/adapters/naver.py tests/unit/test_blog_scraper_naver.py && git commit -m "feat: add _select_post_hrefs pure function and categoryNo support in naver scraper"
```

---

## Task 2: live DOM 기반 포스트 수집

**Files:**
- Modify: `src/naver_blog_bot/blog_scraper/adapters/naver.py`
- Test: `tests/unit/test_blog_scraper_naver.py`

- [x] **Step 1: import 정리 + fake-page 테스트 교체**

먼저 `tests/unit/test_blog_scraper_naver.py` 상단 import에서 `collect_post_urls`를 제거한다. 현재 import 블록(line 5-14)은:

```python
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
```

여기서 `    collect_post_urls,` 줄을 삭제한다.

그 다음, 기존 `test_collect_blog_post_urls_raises_when_empty` 함수를 아래 두 함수로 교체한다 (이 함수는 `content()` 기반 fake page라 live DOM 구현에서 깨짐):

```python
def test_collect_blog_post_urls_uses_live_dom() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.goto_url: str | None = None

        async def goto(self, url: str, **kwargs: object) -> None:
            self.goto_url = url

        async def wait_for_selector(self, selector: str, **kwargs: object) -> None:
            return None

        async def eval_on_selector_all(self, selector: str, script: str) -> list[str]:
            return [
                "https://m.blog.naver.com/foo/100",
                "https://m.blog.naver.com/foo/100",
                "https://m.blog.naver.com/foo/200",
                "https://example.com/other",
            ]

    page = FakePage()
    urls = asyncio.run(
        collect_blog_post_urls(page, "https://blog.naver.com/foo", 5)
    )
    assert urls == [
        "https://m.blog.naver.com/foo/100",
        "https://m.blog.naver.com/foo/200",
    ]
    assert page.goto_url is not None and "PostList.naver" in page.goto_url


def test_collect_blog_post_urls_raises_when_no_posts() -> None:
    class EmptyPage:
        async def goto(self, url: str, **kwargs: object) -> None:
            return None

        async def wait_for_selector(self, selector: str, **kwargs: object) -> None:
            return None

        async def eval_on_selector_all(self, selector: str, script: str) -> list[str]:
            return ["https://example.com/other"]

    with pytest.raises(ValueError, match="no posts found"):
        asyncio.run(
            collect_blog_post_urls(EmptyPage(), "https://blog.naver.com/foo", 5)
        )
```

- [x] **Step 2: 기존 collect_post_urls 테스트 3개 제거**

같은 파일에서 아래 3개 테스트를 삭제한다 (`collect_post_urls` 함수가 제거되므로):
- `test_collect_post_urls_from_mobile_post_list`
- `test_collect_post_urls_canonicalizes_relative_post_view_link`
- `test_collect_post_urls_canonicalizes_pc_absolute_link`

또한 이제 사용되지 않는 모듈 상수 `POST_LIST_HTML`도 함께 삭제한다 (위 3개 테스트에서만 쓰였다면).

- [x] **Step 3: 실패 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_blog_scraper_naver.py -v 2>&1 | tail -25
```

Expected: 새 live DOM 테스트 FAIL (collect_blog_post_urls가 아직 content() 기반)

- [x] **Step 4: `collect_blog_post_urls` live DOM화 + `collect_post_urls` 제거**

`src/naver_blog_bot/blog_scraper/adapters/naver.py`에서 `collect_post_urls` 함수 전체를 삭제하고, `collect_blog_post_urls`를 아래로 교체:

```python
async def collect_blog_post_urls(page: object, url: str, count: int) -> list[str]:
    list_url = post_list_url(url)
    await page.goto(list_url, wait_until="networkidle")  # type: ignore[attr-defined]
    try:
        await page.wait_for_selector("a", timeout=8000)  # type: ignore[attr-defined]
    except Exception:
        pass
    hrefs: list[str] = await page.eval_on_selector_all(  # type: ignore[attr-defined]
        "a", "els => els.map(e => e.href).filter(Boolean)"
    )
    urls = _select_post_hrefs(hrefs, list_url, count)
    if not urls:
        raise ValueError(f"no posts found at {url}")
    return urls
```

- [x] **Step 5: 통과 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_blog_scraper_naver.py -v
```

Expected: ALL PASS (collect_post_urls 참조 잔존 없음 확인)

- [x] **Step 6: 잔존 참조 검사**

```bash
cd /home/indietogo/projects/naver-blog-bot && grep -rn "collect_post_urls" src/ tests/ || echo "NO_REFERENCES"
```

Expected: `_select_post_hrefs`만 나오고 `collect_post_urls`(단독) 참조는 없어야 함. 남아 있으면 수정.

- [x] **Step 7: 커밋**

```bash
cd /home/indietogo/projects/naver-blog-bot && git add src/naver_blog_bot/blog_scraper/adapters/naver.py tests/unit/test_blog_scraper_naver.py && git commit -m "fix: collect naver post urls from live DOM instead of static HTML parser"
```

---

## Task 4: 엔드포인트 수정 (진짜 근본원인) + 렌더 폴링

> probe 확정: `PostList.naver`(레거시)는 posts=0, `m.blog.naver.com/{id}`(모바일 홈)는 posts=31. 엔드포인트를 모바일 홈으로 변경.

**Files:**
- Modify: `src/naver_blog_bot/blog_scraper/adapters/naver.py`
- Test: `tests/unit/test_blog_scraper_naver.py`

- [x] **Step 1: 기존/신규 테스트를 새 엔드포인트 기대값으로 갱신**

`tests/unit/test_blog_scraper_naver.py`에서 아래 테스트들을 수정/추가한다.

기존 `test_post_list_url_builds_mobile_post_list_url`를 교체:
```python
def test_post_list_url_builds_mobile_blog_home() -> None:
    assert naver.post_list_url("https://blog.naver.com/myid") == "https://m.blog.naver.com/myid"
```

기존 `test_post_list_url_preserves_category_no`를 교체 (blogId는 이제 path에 있음):
```python
def test_post_list_url_preserves_category_no() -> None:
    url = naver.post_list_url("https://blog.naver.com/foo?categoryNo=7")
    assert url == "https://m.blog.naver.com/foo?categoryNo=7"
```

`test_post_list_url_without_category_has_no_category_param`는 그대로 유지 (여전히 통과해야 함).

폴링 동작 검증을 위해 기존 `test_collect_blog_post_urls_uses_live_dom`의 FakePage에 `wait_for_timeout` 메서드를 추가하고, `test_collect_blog_post_urls_raises_when_no_posts`의 EmptyPage에도 추가한다. 두 FakePage 모두에 다음 메서드를 추가:
```python
        async def wait_for_timeout(self, ms: int) -> None:
            return None
```
그리고 live_dom 테스트의 기대 URL 검증을 엔드포인트 변경에 맞춰 수정:
```python
    assert page.goto_url == "https://m.blog.naver.com/foo"
```

폴링 재시도 검증 테스트 신규 추가:
```python
def test_collect_blog_post_urls_polls_until_posts_appear() -> None:
    class LatePage:
        def __init__(self) -> None:
            self.calls = 0

        async def goto(self, url: str, **kwargs: object) -> None:
            return None

        async def wait_for_timeout(self, ms: int) -> None:
            return None

        async def eval_on_selector_all(self, selector: str, script: str) -> list[str]:
            self.calls += 1
            if self.calls < 3:
                return ["https://example.com/nav"]
            return ["https://m.blog.naver.com/foo/100"]

    page = LatePage()
    urls = asyncio.run(collect_blog_post_urls(page, "https://blog.naver.com/foo", 5))
    assert urls == ["https://m.blog.naver.com/foo/100"]
    assert page.calls >= 3
```

- [x] **Step 2: 실패 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_blog_scraper_naver.py -v 2>&1 | tail -25
```
Expected: 엔드포인트/폴링 테스트 FAIL.

- [x] **Step 3: `post_list_url` 엔드포인트 변경**

`src/naver_blog_bot/blog_scraper/adapters/naver.py`의 `post_list_url`을 아래로 교체:
```python
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
    result = parsed._replace(
        path=f"/{blog_id}", query=urlencode(query), fragment=""
    )
    return urlunparse(result)
```

- [x] **Step 4: `collect_blog_post_urls` 폴링 추가**

`collect_blog_post_urls`를 아래로 교체:
```python
async def collect_blog_post_urls(page: object, url: str, count: int) -> list[str]:
    list_url = post_list_url(url)
    await page.goto(list_url, wait_until="networkidle")  # type: ignore[attr-defined]
    urls: list[str] = []
    for attempt in range(5):
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
```

- [x] **Step 5: 통과 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_blog_scraper_naver.py -v
```
Expected: ALL PASS.

- [x] **Step 6: 커밋**

```bash
cd /home/indietogo/projects/naver-blog-bot && git add src/naver_blog_bot/blog_scraper/adapters/naver.py tests/unit/test_blog_scraper_naver.py && git commit -m "fix: use mobile blog home endpoint and poll for late-rendered post anchors"
```

---

## Task 5: naver-bot login 명령 (headed 세션)

**Files:**
- Create: `src/naver_blog_bot/blog_scraper/login.py`
- Modify: `src/naver_blog_bot/cli.py`
- Test: `tests/unit/test_login.py`

- [x] **Step 1: login 헬퍼 테스트 작성**

`tests/unit/test_login.py` 신규:
```python
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

    with patch(
        "naver_blog_bot.blog_scraper.login.async_playwright", side_effect=_PW
    ):
        asyncio.run(run_login(settings, wait_for_user=AsyncMock()))

    assert launch_kwargs["user_data_dir"] == str(tmp_path)
    assert launch_kwargs["headless"] is False
    page.goto.assert_awaited()
    ctx.close.assert_awaited_once()
```

- [x] **Step 2: 실패 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_login.py -v 2>&1 | tail -15
```
Expected: FAIL (`login.py` 없음).

- [x] **Step 3: login.py 구현**

`src/naver_blog_bot/blog_scraper/login.py` 신규:
```python
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from playwright.async_api import async_playwright

from naver_blog_bot.config import Settings

_LOGIN_URL = "https://nid.naver.com/nidlogin.login"


async def _default_wait_for_user() -> None:
    # Block on the user pressing Enter in the terminal without blocking the loop.
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
```

- [x] **Step 4: cli.py에 login 명령 추가**

`src/naver_blog_bot/cli.py` 상단 import에 추가:
```python
from naver_blog_bot.blog_scraper.login import run_login
```
그리고 `init_command` 다음에 추가:
```python
@app.command("login")
def login_command() -> None:
    import asyncio

    settings = get_settings()
    ensure_local_directories(settings)
    typer.echo("브라우저 창에서 네이버에 로그인하세요. 완료 후 터미널에서 Enter.")
    asyncio.run(run_login(settings))
    typer.echo(f"로그인 세션이 저장되었습니다: {settings.browser_profile_dir}")
```

- [x] **Step 5: 통과 확인 + 명령 등록 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_login.py -v && uv run naver-bot --help 2>&1 | grep login
```
Expected: 테스트 PASS, `--help`에 `login` 표시.

- [x] **Step 6: ADR append**

`docs/ai-context/architecture.md` ADR 섹션에 append:
```markdown
### ADR-005: Headed manual login for Naver session

- 날짜: 2026-05-30
- 상태: Accepted
- 결정: `naver-bot login`이 headed(headless=False) persistent Chromium을 `browser-profile/`로 띄워 사용자가 직접 네이버에 로그인하고, 세션을 디스크에 저장한다. 이후 `profile-refresh`가 같은 프로필을 재사용한다.
- 이유: 공개 글은 로그아웃 상태로도 스크래핑되지만(모바일 홈 엔드포인트), 비공개·이웃공개 글과 세션 안정성을 위해 로그인된 컨텍스트가 필요하다. 자동 자격증명 입력은 CAPTCHA/2FA·ToS 위험이 있어 사람이 직접 로그인한다.
- 대안: API 키만 사용; headless 자동 로그인; 로그인 없이 공개 글만 지원.
- 트레이드오프: WSLg 등 디스플레이가 필요하고 1회 수동 단계가 생기지만, 자동화 탐지·계정 위험을 피하고 비공개 글 학습을 가능케 한다.
```

또한 모듈 그래프에 `blog_scraper --> login["blog_scraper/login.py"]` 와 `cli --> login` 추가.

- [x] **Step 7: 커밋**

```bash
cd /home/indietogo/projects/naver-blog-bot && git add src/naver_blog_bot/blog_scraper/login.py src/naver_blog_bot/cli.py tests/unit/test_login.py docs/ai-context/architecture.md && git commit -m "feat: add naver-bot login command for headed manual Naver session"
```

---

## Task 6: 최종 검증 + 실제 블로그 스모크

**Files:**
- Verify: 변경 파일 전체

- [x] **Step 1: 전체 품질 게이트**

```bash
cd /home/indietogo/projects/naver-blog-bot && bash scripts/check.sh
```
Expected: exit 0.

- [x] **Step 2: 실제 블로그 URL 수집 스모크 (Claude 호출 없음)**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run python3 -c "
from naver_blog_bot.blog_scraper.service import scrape
from naver_blog_bot.config import Settings
docs = scrape('https://blog.naver.com/flowerbend', 3, Settings())
print('COLLECTED', len(docs))
for d in docs: print('-', (d.title or '')[:40], len(d.to_structured_text()))
"
```
Expected: `COLLECTED 3` + 각 포스트 제목/길이. (모바일 홈 엔드포인트로 공개 글 수집)

실패 시 → probe로 확인된 모바일 홈 엔드포인트/폴링 점검.

- [x] **Step 3: (선택) 실제 profile-refresh 스모크 (Claude 호출)**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run naver-bot profile-refresh "https://blog.naver.com/flowerbend" --count 3
```
Expected: `Style profile saved` + `default-examples.json` 생성.

- [x] **Step 4: 명시 요청 없이는 추가 커밋 금지**

---

## Self-Review

- **Spec 커버리지:** live DOM 수집(Task 2) / 순수 함수 분리(Task 1) / categoryNo(Task 1) / 본문 파서 불변 / 오프라인 테스트 유지 — 모두 커버.
- **Placeholder 없음:** 모든 코드 단계에 실제 코드 포함. (Step 3의 `<N>`/`<category-name>`은 사용자 입력 값으로 의도된 자리.)
- **타입 일관성:** `_select_post_hrefs(hrefs, base_url, count)` Task 1 정의 → Task 2에서 사용. `collect_post_urls` 제거 시 import 정리(Task 2 Step 1) + 테스트 3개 삭제(Step 2) + 참조 잔존 검사(Step 6) 포함.
- **이름 검증:** plan이 참조하는 테스트 이름은 모두 실제 `tests/unit/test_blog_scraper_naver.py`에 존재하는 이름(`test_collect_post_urls_from_mobile_post_list` 등)과 일치하도록 정정됨.
- **범위:** naver.py + 해당 테스트만. tistory/로그인/service·cli 시그니처 불변.
