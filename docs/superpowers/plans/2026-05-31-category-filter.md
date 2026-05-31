**Status:** completed
**RPI-Cycle:** 8
**Started:** 2026-05-31

# Naver Category Filter via PostTitleListAsync API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [x]`) syntax.

**Goal:** `profile-refresh ...?categoryNo=N`이 해당 카테고리 글만 수집하도록, probe로 검증된 `PostTitleListAsync.naver` JSON API 경로를 `collect_blog_post_urls`에 추가한다. categoryNo 없으면 기존 모바일 홈 경로 유지.

**Architecture:** `blog_scraper/adapters/naver.py`만 변경. JSON URL 생성과 파싱을 순수 함수로 분리해 오프라인 테스트를 유지하고, `collect_blog_post_urls`는 categoryNo 유무로 분기. 본문 파서·시그니처 불변.

**Tech Stack:** Python 3.11+, Playwright(async), pytest, ruff.

---

## 확정된 사실 (probe 검증)

- `blog.naver.com/PostTitleListAsync.naver?blogId={id}&categoryNo={N}&countPerPage=30&currentPage=1` → JSON 반환, categoryNo 정확히 필터 (맛집 cat10=5개, 연애 cat6=2개).
- JSON 형태: `{"resultCode":"S","postList":[{"logNo":"224291881837","categoryNo":"10",...}, ...],"totalCount":"5"}`
- 포스트 URL은 `https://m.blog.naver.com/{blogId}/{logNo}`로 구성 → 기존 `scrape_post`가 그대로 처리.
- same-origin fetch 필요: `blog.naver.com` 홈으로 goto 후 `page.evaluate(fetch(...))`.

---

## Task 1: 순수 함수 — URL 생성 + JSON 파싱

**Files:**
- Modify: `src/naver_blog_bot/blog_scraper/adapters/naver.py`
- Test: `tests/unit/test_blog_scraper_naver.py`

- [x] **Step 1: 실패 테스트 추가**

`tests/unit/test_blog_scraper_naver.py`에 추가:

```python
def test_category_list_api_url_with_category() -> None:
    url = naver.category_list_api_url("https://blog.naver.com/flowerbend?categoryNo=10")
    assert url is not None
    assert "PostTitleListAsync.naver" in url
    assert "blogId=flowerbend" in url
    assert "categoryNo=10" in url


def test_category_list_api_url_without_category_returns_none() -> None:
    assert naver.category_list_api_url("https://blog.naver.com/flowerbend") is None


def test_select_post_urls_from_titlelist_builds_mobile_urls() -> None:
    payload = {
        "resultCode": "S",
        "postList": [
            {"logNo": "224291881837", "categoryNo": "10"},
            {"logNo": "224141677589", "categoryNo": "10"},
        ],
        "totalCount": "5",
    }
    urls = naver._select_post_urls_from_titlelist(payload, "flowerbend", 5)
    assert urls == [
        "https://m.blog.naver.com/flowerbend/224291881837",
        "https://m.blog.naver.com/flowerbend/224141677589",
    ]


def test_select_post_urls_from_titlelist_respects_count() -> None:
    payload = {
        "postList": [
            {"logNo": "1"},
            {"logNo": "2"},
            {"logNo": "3"},
        ]
    }
    urls = naver._select_post_urls_from_titlelist(payload, "foo", 2)
    assert urls == [
        "https://m.blog.naver.com/foo/1",
        "https://m.blog.naver.com/foo/2",
    ]


def test_select_post_urls_from_titlelist_empty() -> None:
    assert naver._select_post_urls_from_titlelist({"postList": []}, "foo", 5) == []
```

- [x] **Step 2: 실패 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_blog_scraper_naver.py -k "titlelist or category_list_api" -v 2>&1 | tail -20
```
Expected: FAIL (함수 없음).

- [x] **Step 3: 두 순수 함수 구현**

`src/naver_blog_bot/blog_scraper/adapters/naver.py`에서 `_select_post_hrefs` 함수 바로 아래에 추가:

```python
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
```

- [x] **Step 4: 통과 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_blog_scraper_naver.py -k "titlelist or category_list_api" -v
```
Expected: PASS.

- [x] **Step 5: 커밋**

```bash
cd /home/indietogo/projects/naver-blog-bot && git add src/naver_blog_bot/blog_scraper/adapters/naver.py tests/unit/test_blog_scraper_naver.py && git commit -m "feat: add category_list_api_url and titlelist parser for naver category filter"
```

---

## Task 2: collect_blog_post_urls categoryNo 분기

**Files:**
- Modify: `src/naver_blog_bot/blog_scraper/adapters/naver.py`
- Test: `tests/unit/test_blog_scraper_naver.py`

- [x] **Step 1: 분기 mock 테스트 추가**

`tests/unit/test_blog_scraper_naver.py`에 추가:

```python
def test_collect_blog_post_urls_category_uses_json_api() -> None:
    import json

    class CatPage:
        def __init__(self) -> None:
            self.goto_url: str | None = None
            self.evaluated: list[str] = []

        async def goto(self, url: str, **kwargs: object) -> None:
            self.goto_url = url

        async def wait_for_timeout(self, ms: int) -> None:
            return None

        async def eval_on_selector_all(self, selector: str, script: str) -> list[str]:
            raise AssertionError("category path must not use DOM anchors")

        async def evaluate(self, script: str, arg: object = None) -> str:
            self.evaluated.append(str(arg))
            return json.dumps(
                {
                    "resultCode": "S",
                    "postList": [
                        {"logNo": "100", "categoryNo": "10"},
                        {"logNo": "200", "categoryNo": "10"},
                    ],
                    "totalCount": "2",
                }
            )

    page = CatPage()
    urls = asyncio.run(
        collect_blog_post_urls(
            page, "https://blog.naver.com/flowerbend?categoryNo=10", 5
        )
    )
    assert urls == [
        "https://m.blog.naver.com/flowerbend/100",
        "https://m.blog.naver.com/flowerbend/200",
    ]
    # evaluate was called with the PostTitleListAsync URL
    assert any("PostTitleListAsync.naver" in e for e in page.evaluated)


def test_collect_blog_post_urls_category_naver_prefix_json() -> None:
    class CatPage:
        async def goto(self, url: str, **kwargs: object) -> None:
            return None

        async def wait_for_timeout(self, ms: int) -> None:
            return None

        async def evaluate(self, script: str, arg: object = None) -> str:
            # Naver sometimes prefixes JSON with )]}',
            return ')]}\',\n{"postList":[{"logNo":"55"}]}'

    urls = asyncio.run(
        collect_blog_post_urls(
            CatPage(), "https://blog.naver.com/foo?categoryNo=6", 5
        )
    )
    assert urls == ["https://m.blog.naver.com/foo/55"]


def test_collect_blog_post_urls_category_raises_when_empty() -> None:
    class CatPage:
        async def goto(self, url: str, **kwargs: object) -> None:
            return None

        async def wait_for_timeout(self, ms: int) -> None:
            return None

        async def evaluate(self, script: str, arg: object = None) -> str:
            return '{"postList":[]}'

    with pytest.raises(ValueError, match="no posts found"):
        asyncio.run(
            collect_blog_post_urls(
                CatPage(), "https://blog.naver.com/foo?categoryNo=6", 5
            )
        )
```

- [x] **Step 2: 실패 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_blog_scraper_naver.py -k "category_uses_json or category_naver_prefix or category_raises" -v 2>&1 | tail -20
```
Expected: FAIL (분기 없음; 현재는 categoryNo도 DOM 경로).

- [x] **Step 3: collect_blog_post_urls에 분기 추가**

`src/naver_blog_bot/blog_scraper/adapters/naver.py` 상단 import에 `json` 추가 (이미 있으면 생략). 현재 import는 `import re` 뿐이므로:

```python
import json
import re
```

`collect_blog_post_urls`를 아래로 교체:

```python
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


def _parse_naver_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith(")]}'"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[4:]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("Naver category API returned invalid JSON") from exc
    return data


async def _collect_category_post_urls(
    page: object, url: str, api_url: str, count: int
) -> list[str]:
    parsed = urlparse(normalize_naver_url(url))
    segments = [s for s in parsed.path.split("/") if s]
    blog_id = segments[0] if segments else ""
    # Establish same-origin cookies before fetching the JSON API.
    await page.goto(f"https://{_PC_HOST}/{blog_id}", wait_until="networkidle")  # type: ignore[attr-defined]
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
```

- [x] **Step 4: 통과 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_blog_scraper_naver.py -v 2>&1 | tail -30
```
Expected: ALL PASS (기존 DOM 테스트 + 신규 category 테스트).

- [x] **Step 5: 전체 테스트 + ruff**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/ -q 2>&1 | tail -3 && uv run ruff check src/ tests/
```
Expected: ALL PASS + ruff clean.

- [x] **Step 6: 커밋**

```bash
cd /home/indietogo/projects/naver-blog-bot && git add src/naver_blog_bot/blog_scraper/adapters/naver.py tests/unit/test_blog_scraper_naver.py && git commit -m "feat: route categoryNo profile-refresh through PostTitleListAsync JSON API"
```

---

## Task 3: 최종 검증 + 실제 카테고리 스모크

**Files:**
- Verify: 변경 파일 전체

- [x] **Step 1: 품질 게이트**

```bash
cd /home/indietogo/projects/naver-blog-bot && bash scripts/check.sh
```
Expected: exit 0.

- [x] **Step 2: 실제 카테고리 필터 스모크 (Claude 호출 없음)**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run python3 -c "
from naver_blog_bot.blog_scraper.service import scrape
from naver_blog_bot.config import Settings
s = Settings()
food = scrape('https://blog.naver.com/flowerbend?categoryNo=10', 5, s)
love = scrape('https://blog.naver.com/flowerbend?categoryNo=6', 5, s)
print('food(맛집):', len(food), [d.url.split('/')[-1] for d in food])
print('love(연애):', len(love), [d.url.split('/')[-1] for d in love])
print('DIFFERENT:', set(d.url for d in food) != set(d.url for d in love))
"
```
Expected: food와 love가 **서로 다른** logNo 집합. food=5개(맛집), love=2개(연애).

- [x] **Step 3: 명시 요청 없이는 추가 커밋 금지**

---

## Self-Review

- **Spec 커버리지:** categoryNo 분기(Task 2) / JSON URL·파서 순수 함수(Task 1) / 본문 파서 불변 / 오프라인 테스트.
- **Placeholder 없음:** 모든 단계 실제 코드.
- **타입 일관성:** `category_list_api_url(url)`, `_select_post_urls_from_titlelist(payload, blog_id, count)` Task 1 정의 → Task 2에서 사용. `_collect_category_post_urls`, `_parse_naver_json` Task 2 신규.
- **범위:** naver.py + 테스트만. 시그니처·본문 파서 불변.
