# Scraper Fixture Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** active
**RPI-Cycle:** 14
**Started:** 2026-06-06

**Goal:** Add recorded-fixture characterization tests for the Naver adapter's URL-collection parsers so that a change in Naver's response shape (rendered mobile-home DOM or `PostTitleListAsync.naver` JSON) is caught by a failing unit test, with zero network and no Playwright.

**Architecture:** The four target parsers are already pure functions (`naver._select_post_hrefs`, `naver._select_post_urls_from_titlelist`, `naver._parse_naver_json`, plus `html.parse_html`/`select_all` for anchor extraction). This cycle adds **test data files + one test module only** — no source change, no new dependency, no ADR. Fixtures are deliberately richer than the existing inline synthetic snippets in `test_blog_scraper_naver.py`: anchor soup with multiple URL forms + dedup, the `)]}'` XSSI prefix, full post-field payloads, and a `pagingHtml` blob with invalid `\'` escapes that forces the `json.loads`→regex fallback. This is the early-warning net for the most fragile subsystem (ADR-005/006).

**Tech Stack:** Python 3.11+, pytest, stdlib HTML parser (`blog_scraper/adapters/html.py`). No new libraries.

---

## File Structure

- Create: `tests/unit/fixtures/naver/mobile_home.html` — rendered mobile-home DOM snapshot (anchor soup; 4 unique posts across card/PostView/PC-host forms + dupes + nav/category/external/js/`#`).
- Create: `tests/unit/fixtures/naver/mobile_home_empty.html` — chrome-only home (no post anchors).
- Create: `tests/unit/fixtures/naver/posttitlelist_category.json` — clean PostTitleListAsync response with `)]}'` prefix + full fields (3 posts).
- Create: `tests/unit/fixtures/naver/posttitlelist_paginghtml.json` — response whose `pagingHtml` has invalid `\'` escapes (breaks `json.loads`) → regex fallback recovers 2 logNos.
- Create: `tests/unit/fixtures/naver/posttitlelist_empty.json` — empty `postList` (resultCode N).
- Create: `tests/unit/fixtures/naver/posttitlelist_garbage.json` — HTML error page, no logNo → clear `ValueError`.
- Create: `tests/unit/test_blog_scraper_naver_fixtures.py` — 8 fixture-driven tests + 2 helpers.

Base URL used everywhere: `naver.post_list_url("https://blog.naver.com/flowerbend")` == `https://m.blog.naver.com/flowerbend`. All `blogId`/`logNo` values are synthetic (no PII).

---

## Task 1: Create the recorded fixtures

**Files:**
- Create: `tests/unit/fixtures/naver/mobile_home.html`
- Create: `tests/unit/fixtures/naver/mobile_home_empty.html`
- Create: `tests/unit/fixtures/naver/posttitlelist_category.json`
- Create: `tests/unit/fixtures/naver/posttitlelist_paginghtml.json`
- Create: `tests/unit/fixtures/naver/posttitlelist_empty.json`
- Create: `tests/unit/fixtures/naver/posttitlelist_garbage.json`

- [ ] **Step 1: Write `mobile_home.html`**

Anchor source order yields resolved-unique post URLs `[223456789, 223456700, 223456611, 223456500]` after dedup (post1 card == post1 PostView; post2 card == post2 dup):

```html
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"><title>flowerbend : 네이버 블로그</title></head>
<body>
  <nav class="blog_gnb">
    <a href="https://m.blog.naver.com/">네이버 블로그 홈</a>
    <a href="#">메뉴</a>
    <a href="javascript:void(0)">검색</a>
    <a href="/flowerbend?categoryNo=5">맛집 (12)</a>
    <a href="/flowerbend?categoryNo=2">연애 (4)</a>
  </nav>
  <main class="post_list">
    <div class="post_card">
      <a href="/flowerbend/223456789">제주 오션뷰 카페 후기</a>
      <a href="https://m.blog.naver.com/PostView.naver?blogId=flowerbend&amp;logNo=223456789&amp;widgetTypeCall=true#comment">댓글 12</a>
    </div>
    <div class="post_card">
      <a href="https://m.blog.naver.com/flowerbend/223456700">성수동 디저트 맛집</a>
    </div>
    <div class="post_card">
      <a href="https://blog.naver.com/flowerbend/223456611">홍대 브런치 다녀왔어요</a>
    </div>
    <div class="post_card">
      <a href="/PostView.naver?blogId=flowerbend&amp;logNo=223456500">예전에 쓴 글</a>
    </div>
    <div class="post_card">
      <a href="/flowerbend/223456700">성수동 디저트 맛집 (사진 더보기)</a>
    </div>
  </main>
  <footer class="blog_footer">
    <a href="https://section.blog.naver.com/BlogHome.naver">블로그 홈</a>
    <a href="https://help.naver.com/">고객센터</a>
    <a href="https://blog.naver.com/anotheruser">이웃 블로그</a>
    <a href="https://nid.naver.com/nidlogin.login">로그인</a>
  </footer>
</body>
</html>
```

- [ ] **Step 2: Write `mobile_home_empty.html`** (chrome only, no post anchors)

```html
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"><title>flowerbend : 네이버 블로그</title></head>
<body>
  <nav class="blog_gnb">
    <a href="https://m.blog.naver.com/">네이버 블로그 홈</a>
    <a href="#">메뉴</a>
    <a href="javascript:void(0)">검색</a>
    <a href="/flowerbend?categoryNo=99">빈 카테고리 (0)</a>
  </nav>
  <main class="post_list">
    <p class="empty_message">등록된 글이 없습니다.</p>
  </main>
  <footer class="blog_footer">
    <a href="https://section.blog.naver.com/BlogHome.naver">블로그 홈</a>
    <a href="https://nid.naver.com/nidlogin.login">로그인</a>
  </footer>
</body>
</html>
```

- [ ] **Step 3: Write `posttitlelist_category.json`** (XSSI prefix + valid JSON; `pagingHtml` uses valid `\"` escapes so `json.loads` succeeds)

```
)]}',
{
	"resultCode": "S",
	"resultMessage": "",
	"blogId": "flowerbend",
	"countPerPage": 30,
	"currentPage": 1,
	"totalCount": "5",
	"categoryNo": "10",
	"postList": [
		{"logNo": "223456789", "title": "제주 오션뷰 카페 후기", "addDate": "2026.05.30.", "categoryNo": "10", "commentCount": "12", "sympathyCnt": "44"},
		{"logNo": "223456700", "title": "성수동 디저트 맛집", "addDate": "2026.05.21.", "categoryNo": "10", "commentCount": "3", "sympathyCnt": "20"},
		{"logNo": "223456611", "title": "홍대 브런치 다녀왔어요", "addDate": "2026.05.10.", "categoryNo": "10", "commentCount": "0", "sympathyCnt": "8"}
	],
	"pagingHtml": "<div class=\"blog2_paginate\"><a href=\"#\">1</a></div>"
}
```

- [ ] **Step 4: Write `posttitlelist_paginghtml.json`** — `pagingHtml` contains literal backslash-quote (`\'`), which is an invalid JSON escape and breaks `json.loads`, forcing the `_LOGNO_RE` fallback. No XSSI prefix.

```
{"resultCode":"S","blogId":"flowerbend","totalCount":"5","categoryNo":"10","postList":[{"logNo":"224291881837","title":"가을 제주 3박4일","addDate":"2026.05.01.","categoryNo":"10"},{"logNo":"224141677589","title":"오름 트레킹 후기","addDate":"2026.04.18.","categoryNo":"10"}],"pagingHtml":"<div class=\'blog2_paginate\'><a href=\'?currentPage=1\'>1</a><a href=\'?currentPage=2\'>2</a></div>"}
```

NOTE: the `\'` sequences must be written as literal backslash + single-quote bytes in the file. Step 5 of Task 2 verifies (via `json.JSONDecodeError`) that this fixture is genuinely the broken-shape case.

- [ ] **Step 5: Write `posttitlelist_empty.json`** (plain JSON, empty postList)

```
{"resultCode":"N","resultMessage":"카테고리에 등록된 글이 없습니다.","blogId":"flowerbend","categoryNo":"77","totalCount":"0","postList":[]}
```

- [ ] **Step 6: Write `posttitlelist_garbage.json`** (HTML error page — no logNo)

```
<!DOCTYPE html>
<html><head><title>네이버 : 로그인</title></head>
<body><div class="error_content">유효하지 않은 요청이거나 로그인이 필요합니다.</div></body></html>
```

---

## Task 2: Create the fixture-driven test module

**Files:**
- Create: `tests/unit/test_blog_scraper_naver_fixtures.py`
- Test target: `src/naver_blog_bot/blog_scraper/adapters/naver.py` (pure parsers, unchanged)

- [ ] **Step 1: Write the test module (helpers + 8 tests)**

```python
import json
from pathlib import Path

import pytest

from naver_blog_bot.blog_scraper.adapters import naver
from naver_blog_bot.blog_scraper.adapters.html import parse_html, select_all

_FIXTURES = Path(__file__).parent / "fixtures" / "naver"
_BASE = naver.post_list_url("https://blog.naver.com/flowerbend")


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _hrefs_from_html(html: str) -> list[str]:
    root = parse_html(html)
    return [a.attrs.get("href", "") for a in select_all(root, "a")]


# --- rendered mobile-home DOM (categoryNo absent → live-DOM anchor path) ---


def test_mobile_home_fixture_extracts_unique_post_urls() -> None:
    hrefs = _hrefs_from_html(_load("mobile_home.html"))
    urls = naver._select_post_hrefs(hrefs, _BASE, 10)
    assert urls == [
        "https://m.blog.naver.com/flowerbend/223456789",
        "https://m.blog.naver.com/flowerbend/223456700",
        "https://m.blog.naver.com/flowerbend/223456611",
        "https://m.blog.naver.com/flowerbend/223456500",
    ]


def test_mobile_home_fixture_respects_count() -> None:
    hrefs = _hrefs_from_html(_load("mobile_home.html"))
    urls = naver._select_post_hrefs(hrefs, _BASE, 2)
    assert urls == [
        "https://m.blog.naver.com/flowerbend/223456789",
        "https://m.blog.naver.com/flowerbend/223456700",
    ]


def test_mobile_home_empty_fixture_returns_no_urls() -> None:
    hrefs = _hrefs_from_html(_load("mobile_home_empty.html"))
    assert naver._select_post_hrefs(hrefs, _BASE, 10) == []


# --- PostTitleListAsync JSON (categoryNo present → JSON API path) ---


def test_posttitlelist_category_fixture_extracts_urls() -> None:
    payload = naver._parse_naver_json(_load("posttitlelist_category.json"))
    urls = naver._select_post_urls_from_titlelist(payload, "flowerbend", 10)
    assert urls == [
        "https://m.blog.naver.com/flowerbend/223456789",
        "https://m.blog.naver.com/flowerbend/223456700",
        "https://m.blog.naver.com/flowerbend/223456611",
    ]


def test_posttitlelist_category_fixture_respects_count() -> None:
    payload = naver._parse_naver_json(_load("posttitlelist_category.json"))
    urls = naver._select_post_urls_from_titlelist(payload, "flowerbend", 2)
    assert urls == [
        "https://m.blog.naver.com/flowerbend/223456789",
        "https://m.blog.naver.com/flowerbend/223456700",
    ]


def test_posttitlelist_paginghtml_fixture_recovers_via_regex() -> None:
    raw = _load("posttitlelist_paginghtml.json")
    # Confirm the fixture really is the broken-shape case (invalid \' escape).
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw)
    payload = naver._parse_naver_json(raw)
    urls = naver._select_post_urls_from_titlelist(payload, "flowerbend", 10)
    assert urls == [
        "https://m.blog.naver.com/flowerbend/224291881837",
        "https://m.blog.naver.com/flowerbend/224141677589",
    ]


def test_posttitlelist_empty_fixture_returns_no_urls() -> None:
    payload = naver._parse_naver_json(_load("posttitlelist_empty.json"))
    assert naver._select_post_urls_from_titlelist(payload, "flowerbend", 10) == []


def test_posttitlelist_garbage_fixture_raises_clear_error() -> None:
    raw = _load("posttitlelist_garbage.json")
    with pytest.raises(ValueError, match="invalid JSON"):
        naver._parse_naver_json(raw)
```

- [ ] **Step 2: Run the new module, confirm all 8 pass**

Run: `cd /home/indietogo/projects/naver-blog-bot && export PATH="/home/indietogo/.local/bin:$PATH" && uv run pytest tests/unit/test_blog_scraper_naver_fixtures.py -v`
Expected: `8 passed`. If `test_posttitlelist_paginghtml_fixture_recovers_via_regex` fails at the `pytest.raises(json.JSONDecodeError)` line, the `\'` escape was not written literally — re-write Task 1 Step 4 ensuring a backslash precedes each single quote.

- [ ] **Step 3: Confirm fixtures are non-vacuous (anchor soup actually filtered)**

The `mobile_home.html` extraction must include nav/category/external/js/`#`/duplicate anchors that are all excluded. Sanity: the raw href list has > 10 entries but resolves to exactly 4 posts. This is asserted implicitly by the exact-list equality in Step 1 (any leaked nav/external URL would break equality).

---

## Task 3: Full-suite verification gate

- [ ] **Step 1: Run the gate**

Run: `cd /home/indietogo/projects/naver-blog-bot && export PATH="/home/indietogo/.local/bin:$PATH" && bash scripts/check.sh; echo "RC=$?"`
Expected: ruff check passes, `ruff format --check` passes (new file must be pre-formatted), pytest prints `N passed` (171 prior + 8 new = 179), and `== check complete ==`, then `RC=0`.

- [ ] **Step 2: NOBV-002 guard** — explicitly confirm BOTH the `passed` token AND `RC=0` AND the `== check complete ==` marker appear. A bare `RC=0` without the pytest `passed` line means the gate short-circuited; if so, run `uv run ruff format tests/unit/test_blog_scraper_naver_fixtures.py` and re-run the gate.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/fixtures/naver/ tests/unit/test_blog_scraper_naver_fixtures.py docs/superpowers/plans/2026-06-06-scraper-fixture-hardening.md
git commit -m "test: add recorded-fixture characterization tests for Naver URL collection (cycle 14)"
```

---

## Self-Review

- **Spec coverage:** Goal criteria (1) parsers from real fixtures → Task 2 Steps 1 (all 8 tests). (2) categoryNo absent (mobile_home) + present (posttitlelist_category) → tests 1/2/3 + 4/5. (3) graceful broken shape → empty home (test 3), empty postList (test 7), garbage (test 8), regex-recover (test 6). (4) existing suite green → Task 3. (5) check.sh RC=0 → Task 3 Steps 1-2.
- **Placeholder scan:** none — every fixture body and test is literal.
- **Type consistency:** parser names/signatures match `naver.py` (`_select_post_hrefs(hrefs, base_url, count)`, `_select_post_urls_from_titlelist(payload, blog_id, count)`, `_parse_naver_json(raw)`); `post_list_url` returns the mobile base; `select_all(root, "a")` + `node.attrs.get("href")` confirmed against `html.py`.
- **Non-vacuous:** exact-list equality + `json.JSONDecodeError` precondition guard the tests against false-green (NOBV-002 sister lesson).
- **Scope:** test data + one test module only. No source change, no ADR, no dependency. Post-body parsing (`parse_post_html`) intentionally out of scope (goal targets URL collection).
