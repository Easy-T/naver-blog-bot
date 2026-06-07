# flowerbend 종합 프로필 + 짤방 자동 수집·학습 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** flowerbend 전체 글을 1회 스크랩해 텍스트는 종합 스타일 프로필(`flowerbend`)로, 이미지는 주인이 실제 쓰는 짤방 라이브러리로 동시 학습하고, 생성기가 흐름에 맞는 진짜 짤방을 배치하게 만든다.

**Architecture:** ① 스크래퍼가 이미지 URL을 보존하고 전 카테고리·전 글을 열거 → ② 새 `meme_harvester`가 이미지를 다운로드·vision 분류(`is_meme`)·중복제거·자동 등록 → ③ 스타일 프로필에 7번째 축(`meme_usage_patterns`)과 배치 map-reduce 빌드를 추가하고 `profile-refresh`에 짤방 학습을 통합 → ④ 생성기 후보 선별을 frequency 기반으로 보강. 분류 결과를 `[짤방]`/`[사진]`으로 주석한 텍스트가 프로필의 짤방 사용 습관을 학습시킨다.

**Tech Stack:** Python 3.11+, uv, pydantic v2, Playwright(스크래핑), httpx(이미지 다운로드), Pillow, Typer, pytest, ruff. Claude 백엔드는 `shared/claude_client.build_text_completer`(complete_text + complete_vision).

**실행 환경 주의:** 모든 명령은 WSL 안에서 실행한다 — 각 `Run:`/`git` 명령을 다음으로 감싼다:
`wsl.exe -d Ubuntu-24.04 bash -lc 'cd ~/projects/naver-blog-bot && <CMD>'`
한글이 들어가는 커밋 메시지는 인자로 직접 주면 깨질 수 있으니, 영어 머리말 + 짧은 한글이면 OK(아래 커밋 메시지는 그 형태로 작성됨).

**전체 검증:** 각 태스크 후 `uv run pytest -q` 회귀 통과. 최종 `bash scripts/check.sh`(ruff check + ruff format --check + pytest) 통과.

**참조 spec:** `docs/superpowers/specs/2026-06-07-flowerbend-profile-and-meme-harvest-design.md`

---

## Phase P1 — 스크래퍼 기반 (이미지 URL 보존 + 전 카테고리 열거)

### Task 1: `ImageBlock.src` 캡처

**Files:**
- Modify: `src/naver_blog_bot/blog_scraper/models.py` (ImageBlock)
- Modify: `src/naver_blog_bot/blog_scraper/adapters/naver.py` (`_img_block_from_node`)
- Test: `tests/unit/test_blog_scraper_naver.py` (append), `tests/unit/test_blog_scraper_models.py` (append)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/unit/test_blog_scraper_naver.py` 끝에 추가:

```python
def test_image_block_captures_src_url() -> None:
    document = parse_post_html(
        NAVER_SMARTEDITOR_HTML, "https://m.blog.naver.com/myid/223456789"
    )
    images = [b for b in document.blocks if isinstance(b, ImageBlock)]
    assert images[0].src == "https://postfiles.pstatic.net/photo.jpg"
    assert images[1].src == "https://postfiles.pstatic.net/photo2.jpg"


def test_image_block_src_falls_back_to_data_lazy_src() -> None:
    html = (
        '<html><head><title>t : 네이버 블로그</title></head><body>'
        '<div class="se-main-container">'
        '<div class="se-component se-image">'
        '<img data-lazy-src="https://postfiles.pstatic.net/lazy.jpg" alt="lazy"></div>'
        "</div></body></html>"
    )
    document = parse_post_html(html, "https://m.blog.naver.com/myid/1")
    images = [b for b in document.blocks if isinstance(b, ImageBlock)]
    assert images[0].src == "https://postfiles.pstatic.net/lazy.jpg"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_blog_scraper_naver.py::test_image_block_captures_src_url -q`
Expected: FAIL — `AttributeError: 'ImageBlock' object has no attribute 'src'`

- [ ] **Step 3: 구현** — `models.py`의 `ImageBlock`에 `src` 추가:

```python
class ImageBlock(BaseModel):
    type: Literal["image"] = "image"
    alt: str = ""
    src: str = ""
```

`adapters/naver.py`의 `_img_block_from_node`를 수정해 src를 채운다(emoticon 판정은 기존 그대로):

```python
def _img_src(img: HtmlNode) -> str:
    for attr in ("src", "data-lazy-src", "data-src"):
        value = img.attrs.get(attr, "")
        if value:
            return value
    return ""


def _img_block_from_node(img: HtmlNode) -> ImageBlock | EmoticonBlock:
    src = _img_src(img)
    alt = img.attrs.get("alt", "")
    classes = img.attrs.get("class", "")
    if is_emoticon_img_attrs(src, classes):
        return EmoticonBlock(description=alt)
    return ImageBlock(alt=alt, src=src)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_blog_scraper_naver.py -q`
Expected: PASS (신규 2개 포함 전부)

- [ ] **Step 5: 회귀 + 커밋**

Run: `uv run pytest -q`
Expected: PASS (기존 `to_structured_text`는 `[이미지]` 그대로 — src 기본값 ""이라 영향 없음)

```bash
git add src/naver_blog_bot/blog_scraper/models.py src/naver_blog_bot/blog_scraper/adapters/naver.py tests/unit/test_blog_scraper_naver.py
git commit -m "feat: capture ImageBlock.src in naver scraper (P1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 카테고리 목록 endpoint + 파서

**Files:**
- Modify: `src/naver_blog_bot/blog_scraper/adapters/naver.py` (신규 함수 2개)
- Test: `tests/unit/test_blog_scraper_naver.py` (append)

- [ ] **Step 1: 실패하는 테스트 작성**:

```python
def test_category_list_endpoint_builds_api_url() -> None:
    assert (
        naver.category_list_endpoint("https://blog.naver.com/flowerbend")
        == "https://m.blog.naver.com/api/blogs/flowerbend/category-list"
    )
    assert (
        naver.category_list_endpoint("https://m.blog.naver.com/flowerbend?categoryNo=7")
        == "https://m.blog.naver.com/api/blogs/flowerbend/category-list"
    )


def test_parse_category_numbers_extracts_division_and_categories() -> None:
    raw = (
        '{"result":{"mylogCategoryList":['
        '{"categoryNo":10,"categoryName":"결혼 준비"},'
        '{"categoryNo":6,"categoryName":"맛집"}]}}'
    )
    assert naver._parse_category_numbers(raw) == ["10", "6"]


def test_parse_category_numbers_strips_naver_prefix_and_dedupes() -> None:
    raw = ")]}',\n" '{"list":[{"categoryNo":"3"},{"categoryNo":"3"},{"categoryNo":"5"}]}'
    assert naver._parse_category_numbers(raw) == ["3", "5"]


def test_parse_category_numbers_empty_returns_zero_fallback() -> None:
    assert naver._parse_category_numbers("{}") == ["0"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_blog_scraper_naver.py::test_category_list_endpoint_builds_api_url -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'category_list_endpoint'`

- [ ] **Step 3: 구현** — `adapters/naver.py`에 추가(파일 상단 import에 `re`, `json`은 이미 있음):

```python
_CATEGORY_NO_RE = re.compile(r'"categoryNo"\s*:\s*"?(\d+)"?')


def category_list_endpoint(url: str) -> str:
    parsed = urlparse(normalize_naver_url(url))
    segments = [s for s in parsed.path.split("/") if s]
    blog_id = segments[0] if segments else ""
    return f"https://{_MOBILE_HOST}/api/blogs/{blog_id}/category-list"


def _parse_category_numbers(raw: str) -> list[str]:
    cleaned = raw.strip()
    if cleaned.startswith(")]}'"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[4:]
    numbers: list[str] = []
    try:
        data = json.loads(cleaned)
        numbers = [str(n) for n in _walk_category_numbers(data)]
    except json.JSONDecodeError:
        numbers = _CATEGORY_NO_RE.findall(cleaned)
    deduped = list(dict.fromkeys(numbers))
    return deduped or ["0"]


def _walk_category_numbers(node: object) -> list[int]:
    found: list[int] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "categoryNo" and isinstance(value, (int, str)):
                try:
                    found.append(int(value))
                except (TypeError, ValueError):
                    pass
            else:
                found.extend(_walk_category_numbers(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_walk_category_numbers(item))
    return found
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_blog_scraper_naver.py -q`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/naver_blog_bot/blog_scraper/adapters/naver.py tests/unit/test_blog_scraper_naver.py
git commit -m "feat: naver category-list endpoint + category number parser (P1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 카테고리 페이지네이션 + `collect_all_post_urls`

**Files:**
- Modify: `src/naver_blog_bot/blog_scraper/adapters/naver.py`
- Test: `tests/unit/test_blog_scraper_naver.py` (append)

기존 `category_list_api_url(url)`는 `categoryNo`가 URL에 있어야 동작한다. 여기서는 `(blog_id, category_no, page)`로 직접 PostTitleListAsync URL을 만드는 보조 함수와, category-list로 모든 카테고리를 받아 각 카테고리를 페이지네이션해 logNo를 모으는 함수를 추가한다.

- [ ] **Step 1: 실패하는 테스트 작성**:

```python
def test_title_list_api_url_for_category_and_page() -> None:
    url = naver._title_list_api_url("flowerbend", "10", 2)
    assert "PostTitleListAsync.naver" in url
    assert "blogId=flowerbend" in url
    assert "categoryNo=10" in url
    assert "currentPage=2" in url


def test_collect_all_post_urls_paginates_each_category() -> None:
    import json

    pages = {
        ("10", 1): {"postList": [{"logNo": "1"}, {"logNo": "2"}]},
        ("10", 2): {"postList": []},
        ("6", 1): {"postList": [{"logNo": "2"}, {"logNo": "9"}]},
        ("6", 2): {"postList": []},
    }

    class FakePage:
        async def goto(self, url: str, **kwargs: object) -> None:
            return None

        async def wait_for_timeout(self, ms: int) -> None:
            return None

        async def evaluate(self, script: str, arg: object = None) -> str:
            text = str(arg)
            if "category-list" in text:
                return json.dumps({"result": {"mylogCategoryList": [
                    {"categoryNo": 10}, {"categoryNo": 6}]}})
            # PostTitleListAsync: read categoryNo + currentPage from the url
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(text).query)
            cat = qs["categoryNo"][0]
            page_no = int(qs["currentPage"][0])
            return json.dumps(pages[(cat, page_no)])

    urls = asyncio.run(
        naver.collect_all_post_urls(FakePage(), "https://blog.naver.com/flowerbend")
    )
    # logNo 2 는 두 카테고리에 중복 등장 → dedupe, 순서 보존
    assert urls == [
        "https://m.blog.naver.com/flowerbend/1",
        "https://m.blog.naver.com/flowerbend/2",
        "https://m.blog.naver.com/flowerbend/9",
    ]


def test_collect_all_post_urls_raises_when_empty() -> None:
    import json

    class FakePage:
        async def goto(self, url: str, **kwargs: object) -> None:
            return None

        async def wait_for_timeout(self, ms: int) -> None:
            return None

        async def evaluate(self, script: str, arg: object = None) -> str:
            if "category-list" in str(arg):
                return json.dumps({"list": [{"categoryNo": 0}]})
            return json.dumps({"postList": []})

    with pytest.raises(ValueError, match="no posts found"):
        asyncio.run(
            naver.collect_all_post_urls(FakePage(), "https://blog.naver.com/foo")
        )
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_blog_scraper_naver.py::test_collect_all_post_urls_paginates_each_category -q`
Expected: FAIL — `AttributeError: ... has no attribute 'collect_all_post_urls'`

- [ ] **Step 3: 구현** — `adapters/naver.py`에 추가:

```python
_MAX_CATEGORY_PAGES = 100


def _title_list_api_url(blog_id: str, category_no: str, current_page: int) -> str:
    query = urlencode(
        {
            "blogId": blog_id,
            "categoryNo": category_no,
            "countPerPage": 30,
            "currentPage": current_page,
        }
    )
    return f"https://{_PC_HOST}/PostTitleListAsync.naver?{query}"


async def _fetch_json_text(page: object, api_url: str) -> str:
    return await page.evaluate(  # type: ignore[attr-defined]
        """async (apiUrl) => {
            const r = await fetch(apiUrl, {headers: {'Accept': 'application/json'}, credentials: 'include'});
            return await r.text();
        }""",
        api_url,
    )


async def collect_all_post_urls(page: object, url: str) -> list[str]:
    parsed = urlparse(normalize_naver_url(url))
    segments = [s for s in parsed.path.split("/") if s]
    blog_id = segments[0] if segments else ""

    # Establish same-origin cookies first.
    await page.goto(  # type: ignore[attr-defined]
        f"https://{_PC_HOST}/{blog_id}", wait_until="networkidle"
    )

    cat_raw = await _fetch_json_text(page, category_list_endpoint(url))
    category_numbers = _parse_category_numbers(cat_raw)

    log_nos: list[str] = []
    seen: set[str] = set()
    for category_no in category_numbers:
        for current_page in range(1, _MAX_CATEGORY_PAGES + 1):
            api_url = _title_list_api_url(blog_id, category_no, current_page)
            raw = await _fetch_json_text(page, api_url)
            data = _parse_naver_json(raw)
            page_log_nos = [
                str(p["logNo"]) for p in (data.get("postList") or []) if p.get("logNo")
            ]
            if not page_log_nos:
                break
            new_on_page = False
            for log_no in page_log_nos:
                if log_no not in seen:
                    seen.add(log_no)
                    log_nos.append(log_no)
                    new_on_page = True
            if not new_on_page:
                break

    if not log_nos:
        raise ValueError(f"no posts found at {url}")
    return [f"https://{_MOBILE_HOST}/{blog_id}/{log_no}" for log_no in log_nos]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_blog_scraper_naver.py -q`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/naver_blog_bot/blog_scraper/adapters/naver.py tests/unit/test_blog_scraper_naver.py
git commit -m "feat: collect_all_post_urls paginates all categories (P1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 서비스 `scrape_blog_all`

**Files:**
- Modify: `src/naver_blog_bot/blog_scraper/service.py`
- Test: `tests/unit/test_blog_scraper_service.py` (append)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/unit/test_blog_scraper_service.py` 끝에 추가:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_blog_scraper_service.py::test_scrape_blog_all_collects_all_then_scrapes -q`
Expected: FAIL — `ImportError: cannot import name 'scrape_blog_all'`

- [ ] **Step 3: 구현** — `service.py`에 추가(기존 `scrape_blog` 바로 아래). 네이버 전용. 비동기 본체 + 동기 래퍼(CLI용):

```python
async def scrape_blog_all(url: str, settings: Settings) -> list[PostDocument]:
    async with async_playwright() as pw:
        context = await _make_context(pw, naver_persistent=True, settings=settings)
        page = await context.new_page()
        try:
            post_urls = await naver.collect_all_post_urls(page, url)
            results: list[PostDocument] = []
            for i, post_url in enumerate(post_urls):
                if i > 0:
                    await asyncio.sleep(1)
                results.append(await naver.scrape_post(page, post_url))
        finally:
            await context.close()
    return results


def scrape_all(url: str, settings: Settings) -> list[PostDocument]:
    return asyncio.run(scrape_blog_all(url, settings))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_blog_scraper_service.py -q`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/naver_blog_bot/blog_scraper/service.py tests/unit/test_blog_scraper_service.py
git commit -m "feat: scrape_blog_all (all categories, single context) (P1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase P2 — 짤방 수집기

### Task 5: `MemeAsset.frequency` + `MemeIndex.top_by_frequency`

**Files:**
- Modify: `src/naver_blog_bot/meme_library/models.py`
- Test: `tests/unit/test_style_and_memes.py` (append)

- [ ] **Step 1: 실패하는 테스트 작성**:

```python
def test_meme_asset_frequency_defaults_to_one(tmp_path: Path) -> None:
    from naver_blog_bot.meme_library.models import MemeAsset

    asset = MemeAsset(id="x", path=Path("assets/memes/x.png"))
    assert asset.frequency == 1


def test_top_by_frequency_ranks_descending() -> None:
    from naver_blog_bot.meme_library.models import MemeAsset, MemeIndex

    index = MemeIndex(
        memes=[
            MemeAsset(id="rare", path=Path("a.png"), frequency=1),
            MemeAsset(id="common", path=Path("b.png"), frequency=9),
            MemeAsset(id="mid", path=Path("c.png"), frequency=4),
        ]
    )
    top = index.top_by_frequency(limit=2)
    assert [m.id for m in top] == ["common", "mid"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_style_and_memes.py::test_meme_asset_frequency_defaults_to_one -q`
Expected: FAIL — frequency 없음

- [ ] **Step 3: 구현** — `meme_library/models.py`:

`MemeAsset`에 필드 추가:

```python
class MemeAsset(BaseModel):
    id: str
    path: Path
    tags: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    alt_text: str = ""
    frequency: int = 1
```

`MemeIndex`에 메서드 추가(`candidates_for_memo` 아래):

```python
    def top_by_frequency(self, limit: int = 3) -> list["MemeAsset"]:
        ranked = sorted(self.memes, key=lambda m: (-m.frequency, m.id))
        return ranked[:limit]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_style_and_memes.py -q`
Expected: PASS (기존 round-trip 테스트는 frequency 기본값 1로 하위호환)

- [ ] **Step 5: 커밋**

```bash
git add src/naver_blog_bot/meme_library/models.py tests/unit/test_style_and_memes.py
git commit -m "feat: MemeAsset.frequency + MemeIndex.top_by_frequency (P2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 수집기 분류 (`classify_image`) + 모델

**Files:**
- Create: `src/naver_blog_bot/meme_harvester/__init__.py` (빈 파일)
- Create: `src/naver_blog_bot/meme_harvester/models.py`
- Create: `src/naver_blog_bot/meme_harvester/service.py`
- Modify: `src/naver_blog_bot/config.py` (`harvest_cache_path` 프로퍼티)
- Test: `tests/unit/test_meme_harvester.py` (create)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/unit/test_meme_harvester.py` 생성:

```python
from pathlib import Path

from naver_blog_bot.meme_harvester.service import _parse_classification, classify_image


def test_parse_classification_reads_is_meme_and_fields() -> None:
    raw = (
        '{"is_meme": true, "tags": ["놀람"], '
        '"use_cases": ["반전 강조"], "alt_text": "놀란 강아지"}'
    )
    data = _parse_classification(raw)
    assert data["is_meme"] is True
    assert data["tags"] == ["놀람"]
    assert data["use_cases"] == ["반전 강조"]
    assert data["alt_text"] == "놀란 강아지"


def test_parse_classification_defaults_when_garbage() -> None:
    data = _parse_classification("not json")
    assert data["is_meme"] is False
    assert data["tags"] == []


def test_classify_image_passes_context_into_prompt(tmp_path: Path) -> None:
    img = tmp_path / "m.jpg"
    img.write_bytes(b"x")
    seen = {}

    class FakeVision:
        def complete_vision(self, *, image_path, prompt):
            seen["prompt"] = prompt
            return '{"is_meme": true, "tags": ["웃음"], "use_cases": ["유머"], "alt_text": "ㅋㅋ"}'

    data = classify_image(img, FakeVision(), context="너무 웃겨서 빵 터졌어요")
    assert data["is_meme"] is True
    assert "너무 웃겨서 빵 터졌어요" in seen["prompt"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_meme_harvester.py -q`
Expected: FAIL — `ModuleNotFoundError: naver_blog_bot.meme_harvester`

- [ ] **Step 3: 구현**

`src/naver_blog_bot/meme_harvester/__init__.py` — 빈 파일 생성.

`src/naver_blog_bot/meme_harvester/models.py`:

```python
from pydantic import BaseModel, Field

from naver_blog_bot.meme_library.models import MemeAsset


class HarvestResult(BaseModel):
    assets: list[MemeAsset] = Field(default_factory=list)
    meme_srcs: list[str] = Field(default_factory=list)
```

`src/naver_blog_bot/meme_harvester/service.py` (Task 7에서 import를 더 보강함):

```python
import json
from pathlib import Path
from typing import Any

CLASSIFY_PROMPT_HEAD = (
    "이 이미지가 블로그 '짤방'(반응용 밈/움짤/스크린샷/일러스트)인지, "
    "아니면 글의 콘텐츠를 보여주는 실제 촬영 사진인지 한국어로 판단해라.\n"
    "실제 풍경·인물·제품·음식·매장 등을 직접 찍은 사진이면 is_meme=false. "
    "반응을 표현하려고 가져다 쓴 밈/움짤/캡처/그림이면 is_meme=true.\n"
    'JSON만 반환: {"is_meme": true/false, "tags": [...], '
    '"use_cases": [...], "alt_text": "..."}\n'
    "tags: 감정/분위기 키워드 3-6개. use_cases: 이 짤방을 쓰기 좋은 상황 2-4개. "
    "alt_text: 한 줄 설명. JSON 외 텍스트 금지."
)


def _extract_json(raw: str) -> dict[str, Any]:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("not a dict")
    return data


def _parse_classification(raw: str) -> dict[str, Any]:
    try:
        data = _extract_json(raw)
    except (json.JSONDecodeError, ValueError):
        return {"is_meme": False, "tags": [], "use_cases": [], "alt_text": ""}
    return {
        "is_meme": bool(data.get("is_meme", False)),
        "tags": list(data.get("tags", []) or []),
        "use_cases": list(data.get("use_cases", []) or []),
        "alt_text": str(data.get("alt_text", "") or ""),
    }


def classify_image(image_path: Path, vision_client: Any, *, context: str = "") -> dict[str, Any]:
    prompt = CLASSIFY_PROMPT_HEAD
    if context.strip():
        prompt += f"\n\n이 이미지가 사용된 문맥(참고): {context.strip()[:300]}"
    raw = vision_client.complete_vision(image_path=image_path, prompt=prompt)
    return _parse_classification(raw)
```

`src/naver_blog_bot/config.py` — `caption_cache_path` 아래에 추가:

```python
    @property
    def harvest_cache_path(self) -> Path:
        return self.config_dir / ".harvest-cache.json"
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_meme_harvester.py -q`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/naver_blog_bot/meme_harvester/ src/naver_blog_bot/config.py tests/unit/test_meme_harvester.py
git commit -m "feat: meme_harvester classify_image + HarvestResult + harvest cache path (P2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: 수집기 오케스트레이션 `harvest_memes`

**Files:**
- Modify: `src/naver_blog_bot/meme_harvester/service.py`
- Test: `tests/unit/test_meme_harvester.py` (append)

`harvest_memes`는 (a) 문서들의 ImageBlock에서 (src, context) 추출 → (b) URL 캐시 조회 → 미스면 `fetch(url, referer)`로 다운로드 → content-hash → (c) 새 hash면 `classify_image` 1콜 → (d) `is_meme`만 자산화(파일 기록 + MemeAsset), hash로 dedupe + frequency 집계 → (e) `HarvestResult` 반환. `fetch`는 주입식(테스트는 가짜).

- [ ] **Step 1: 실패하는 테스트 작성** — append:

```python
def test_harvest_memes_dedupes_by_hash_and_counts_frequency(tmp_path: Path) -> None:
    from naver_blog_bot.blog_scraper.models import ImageBlock, PostDocument, TextBlock
    from naver_blog_bot.meme_harvester.service import harvest_memes

    # 같은 짤방(bytes 동일)이 두 글에 등장 → frequency 2, 자산 1개
    doc1 = PostDocument(url="https://m.blog.naver.com/f/1", title="t1", blocks=[
        TextBlock(content="웃긴 일이 있었어요"),
        ImageBlock(alt="", src="https://cdn/a.jpg"),
        ImageBlock(alt="", src="https://cdn/photo.jpg"),
    ])
    doc2 = PostDocument(url="https://m.blog.naver.com/f/2", title="t2", blocks=[
        ImageBlock(alt="", src="https://cdn/b.jpg"),  # a.jpg 와 동일 bytes
    ])

    bytes_by_url = {
        "https://cdn/a.jpg": b"MEME-BYTES",
        "https://cdn/b.jpg": b"MEME-BYTES",
        "https://cdn/photo.jpg": b"REAL-PHOTO-BYTES",
    }
    fetch_calls: list[str] = []

    def fake_fetch(url: str, *, referer: str) -> bytes:
        fetch_calls.append(url)
        return bytes_by_url[url]

    class FakeVision:
        def __init__(self) -> None:
            self.calls = 0

        def complete_vision(self, *, image_path, prompt):
            self.calls += 1
            data = image_path.read_bytes()
            if data == b"MEME-BYTES":
                return '{"is_meme": true, "tags": ["웃음"], "use_cases": ["유머"], "alt_text": "ㅋㅋ"}'
            return '{"is_meme": false, "tags": [], "use_cases": [], "alt_text": "사진"}'

    vision = FakeVision()
    cache = tmp_path / ".harvest-cache.json"
    result = harvest_memes(
        [doc1, doc2], vision, memes_dir=tmp_path / "memes",
        cache_path=cache, fetch=fake_fetch,
    )

    assert len(result.assets) == 1
    asset = result.assets[0]
    assert asset.frequency == 2
    assert "웃음" in asset.tags
    assert asset.path.exists()
    assert sorted(result.meme_srcs) == ["https://cdn/a.jpg", "https://cdn/b.jpg"]
    # 3개 URL 모두 1회씩 다운로드, vision 은 distinct hash 2개만
    assert len(fetch_calls) == 3
    assert vision.calls == 2


def test_harvest_memes_cache_hit_skips_fetch_and_vision(tmp_path: Path) -> None:
    from naver_blog_bot.blog_scraper.models import ImageBlock, PostDocument
    from naver_blog_bot.meme_harvester.service import harvest_memes

    doc = PostDocument(url="https://m.blog.naver.com/f/1", title="t", blocks=[
        ImageBlock(alt="", src="https://cdn/a.jpg"),
    ])

    def fetch_once(url: str, *, referer: str) -> bytes:
        return b"MEME"

    class V:
        def __init__(self) -> None:
            self.calls = 0

        def complete_vision(self, *, image_path, prompt):
            self.calls += 1
            return '{"is_meme": true, "tags": ["x"], "use_cases": ["y"], "alt_text": "z"}'

    cache = tmp_path / ".harvest-cache.json"
    v1 = V()
    harvest_memes([doc], v1, memes_dir=tmp_path / "m", cache_path=cache, fetch=fetch_once)
    assert v1.calls == 1

    # 2nd run: same URL → cache hit, no fetch, no vision
    fetch_calls: list[str] = []

    def fetch_track(url: str, *, referer: str) -> bytes:
        fetch_calls.append(url)
        return b"MEME"

    v2 = V()
    result2 = harvest_memes(
        [doc], v2, memes_dir=tmp_path / "m", cache_path=cache, fetch=fetch_track
    )
    assert v2.calls == 0
    assert fetch_calls == []
    assert len(result2.assets) == 1


def test_harvest_memes_skips_download_failures(tmp_path: Path) -> None:
    from naver_blog_bot.blog_scraper.models import ImageBlock, PostDocument
    from naver_blog_bot.meme_harvester.service import harvest_memes

    doc = PostDocument(url="https://m.blog.naver.com/f/1", title="t", blocks=[
        ImageBlock(alt="", src="https://cdn/broken.jpg"),
    ])

    def failing_fetch(url: str, *, referer: str):
        return None

    class V:
        def complete_vision(self, *, image_path, prompt):
            raise AssertionError("should not classify a failed download")

    result = harvest_memes(
        [doc], V(), memes_dir=tmp_path / "m",
        cache_path=tmp_path / "c.json", fetch=failing_fetch,
    )
    assert result.assets == []
    assert result.meme_srcs == []
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_meme_harvester.py::test_harvest_memes_dedupes_by_hash_and_counts_frequency -q`
Expected: FAIL — `ImportError: cannot import name 'harvest_memes'`

- [ ] **Step 3: 구현** — `meme_harvester/service.py`에 추가(상단 import 보강):

```python
import hashlib
from collections.abc import Callable, Sequence
from urllib.parse import urlparse

import httpx

from naver_blog_bot.blog_scraper.models import ImageBlock, PostDocument
from naver_blog_bot.meme_harvester.models import HarvestResult
from naver_blog_bot.meme_library.models import MemeAsset
from naver_blog_bot.storage.json_store import read_json, write_json

FetchFn = Callable[..., "bytes | None"]

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _default_fetch(url: str, *, referer: str) -> bytes | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": referer or "https://m.blog.naver.com/",
    }
    try:
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


def _image_contexts(document: PostDocument) -> list[tuple[str, str]]:
    """Return (src, surrounding_text) for each ImageBlock that has a src."""
    blocks = document.blocks
    out: list[tuple[str, str]] = []
    for i, block in enumerate(blocks):
        if isinstance(block, ImageBlock) and block.src:
            before = ""
            after = ""
            for j in range(i - 1, -1, -1):
                if getattr(blocks[j], "type", "") == "text":
                    before = blocks[j].content
                    break
            for j in range(i + 1, len(blocks)):
                if getattr(blocks[j], "type", "") == "text":
                    after = blocks[j].content
                    break
            out.append((block.src, f"{before} {after}".strip()))
    return out


def _ext_for(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in _IMG_EXTS else ".jpg"


def harvest_memes(
    documents: Sequence[PostDocument],
    vision_client: Any,
    *,
    memes_dir: Path,
    cache_path: Path | None = None,
    fetch: FetchFn | None = None,
) -> HarvestResult:
    fetch = fetch or _default_fetch
    memes_dir.mkdir(parents=True, exist_ok=True)

    cache: dict[str, Any] = {}
    if cache_path is not None and cache_path.exists():
        try:
            cache = read_json(cache_path)
        except Exception:
            cache = {}

    assets_by_hash: dict[str, MemeAsset] = {}
    meme_srcs: list[str] = []
    dirty = False

    for document in documents:
        for src, context in _image_contexts(document):
            entry = cache.get(src)
            if entry is None:
                data = fetch(src, referer=document.url)
                if not data:
                    continue
                digest = hashlib.sha256(data).hexdigest()
                ext = _ext_for(src)
                if digest in assets_by_hash or _hash_in_cache(cache, digest):
                    meta = _meta_for_hash(cache, digest, assets_by_hash)
                else:
                    dest = memes_dir / f"harvested-{digest[:12]}{ext}"
                    dest.write_bytes(data)
                    try:
                        meta = classify_image(dest, vision_client, context=context)
                    except Exception:
                        meta = {"is_meme": False, "tags": [], "use_cases": [], "alt_text": ""}
                    if not meta["is_meme"]:
                        dest.unlink(missing_ok=True)
                    meta = {**meta, "ext": ext}
                entry = {"hash": digest, **meta}
                cache[src] = entry
                dirty = True
            digest = entry["hash"]
            if not entry.get("is_meme"):
                continue
            meme_srcs.append(src)
            existing = assets_by_hash.get(digest)
            if existing is None:
                ext = entry.get("ext", ".jpg")
                assets_by_hash[digest] = MemeAsset(
                    id=f"harvested-{digest[:12]}",
                    path=memes_dir / f"harvested-{digest[:12]}{ext}",
                    tags=list(entry.get("tags", [])),
                    use_cases=list(entry.get("use_cases", [])),
                    alt_text=entry.get("alt_text", ""),
                    frequency=1,
                )
            else:
                assets_by_hash[digest] = existing.model_copy(
                    update={"frequency": existing.frequency + 1}
                )

    if cache_path is not None and dirty:
        write_json(cache_path, cache)

    return HarvestResult(assets=list(assets_by_hash.values()), meme_srcs=meme_srcs)


def _hash_in_cache(cache: dict[str, Any], digest: str) -> bool:
    return any(v.get("hash") == digest for v in cache.values())


def _meta_for_hash(cache: dict[str, Any], digest: str, assets_by_hash: dict[str, MemeAsset]) -> dict[str, Any]:
    if digest in assets_by_hash:
        a = assets_by_hash[digest]
        return {"is_meme": True, "tags": a.tags, "use_cases": a.use_cases,
                "alt_text": a.alt_text, "ext": a.path.suffix}
    for v in cache.values():
        if v.get("hash") == digest:
            return {k: v[k] for k in ("is_meme", "tags", "use_cases", "alt_text", "ext") if k in v}
    return {"is_meme": False, "tags": [], "use_cases": [], "alt_text": "", "ext": ".jpg"}
```

> 주의: `classify_image`/`_parse_classification`는 Task 6에서 정의됨(같은 파일). `Any`는 상단 `from typing import Any`로 import(이미 있음). frequency 집계는 hash별 등장 횟수 — cache-hit 경로에서도 `meme_srcs.append` + frequency 증가가 일어나도록 위 루프가 처리한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_meme_harvester.py -q`
Expected: PASS (3개 신규 + Task6의 3개)

- [ ] **Step 5: 회귀 + 커밋**

Run: `uv run pytest -q`
Expected: PASS

```bash
git add src/naver_blog_bot/meme_harvester/service.py tests/unit/test_meme_harvester.py
git commit -m "feat: harvest_memes — download/hash-dedupe/classify/auto-register (P2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase P3 — 프로필 7축 + 배치 빌드 + CLI 통합

### Task 8: `StyleProfile.meme_usage_patterns` (7번째 축)

**Files:**
- Modify: `src/naver_blog_bot/style_profiler/models.py`
- Test: `tests/unit/test_style_and_memes.py` (append)

- [ ] **Step 1: 실패하는 테스트 작성**:

```python
def test_style_profile_has_meme_usage_patterns_axis() -> None:
    profile = StyleProfile(
        blog_url="https://blog.naver.com/flowerbend",
        meme_usage_patterns=["반전 직후 짤방 1개", "웃긴 에피소드 끝에 움짤"],
    )
    assert profile.meme_usage_patterns == ["반전 직후 짤방 1개", "웃긴 에피소드 끝에 움짤"]
    assert "반전 직후 짤방 1개" in profile.to_cache_text()


def test_meme_usage_patterns_defaults_empty() -> None:
    profile = StyleProfile(blog_url="https://blog.naver.com/flowerbend")
    assert profile.meme_usage_patterns == []
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_style_and_memes.py::test_style_profile_has_meme_usage_patterns_axis -q`
Expected: FAIL — 필드 없음

- [ ] **Step 3: 구현** — `style_profiler/models.py`:

`StyleProfile`에 필드 추가(`emoticon_usage_patterns` 아래):

```python
    meme_usage_patterns: list[str] = Field(default_factory=list)
```

`to_cache_text`의 dict에 키 추가:

```python
        data = {
            "structure_patterns": self.structure_patterns,
            "tone_keywords": self.tone_keywords,
            "frequent_expressions": self.frequent_expressions,
            "review_conventions": self.review_conventions,
            "photo_usage_notes": self.photo_usage_notes,
            "emoticon_usage_patterns": self.emoticon_usage_patterns,
            "meme_usage_patterns": self.meme_usage_patterns,
        }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_style_and_memes.py -q`
Expected: PASS (기존 round-trip/cache 테스트 하위호환 — 기본값 [])

- [ ] **Step 5: 커밋**

```bash
git add src/naver_blog_bot/style_profiler/models.py tests/unit/test_style_and_memes.py
git commit -m "feat: StyleProfile.meme_usage_patterns 7th axis (P3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: refresh 프롬프트/스키마에 7번째 축 + `[짤방]` 인식

**Files:**
- Modify: `src/naver_blog_bot/style_profiler/refresh.py` (SYSTEM_PROMPT)
- Test: `tests/unit/test_profile_refresh.py` (append + VALID_RESPONSE 확장)

- [ ] **Step 1: 실패하는 테스트 작성** — `test_profile_refresh.py`에 추가:

```python
def test_system_prompt_requests_meme_usage_patterns() -> None:
    completer = FakeCompleter(VALID_RESPONSE)
    refresh_style_profile(
        profile_name="default",
        blog_url="https://blog.naver.com/test",
        sample_texts=["[짤방] 빵 터졌어요"],
        completer=completer,
    )
    assert "meme_usage_patterns" in completer.last_system_prompt
    assert "[짤방]" in completer.last_system_prompt


def test_refresh_parses_meme_usage_patterns() -> None:
    response = json.dumps(
        {
            "structure_patterns": ["a"],
            "tone_keywords": ["b"],
            "frequent_expressions": ["c"],
            "review_conventions": ["d"],
            "photo_usage_notes": ["e"],
            "emoticon_usage_patterns": ["f"],
            "meme_usage_patterns": ["반전 직후 짤방"],
        }
    )
    completer = FakeCompleter(response)
    profile = refresh_style_profile(
        profile_name="flowerbend",
        blog_url="https://blog.naver.com/flowerbend",
        sample_texts=["[짤방] 반전!"],
        completer=completer,
    )
    assert profile.meme_usage_patterns == ["반전 직후 짤방"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_profile_refresh.py::test_system_prompt_requests_meme_usage_patterns -q`
Expected: FAIL — 프롬프트에 `meme_usage_patterns` 없음

- [ ] **Step 3: 구현** — `refresh.py`의 `SYSTEM_PROMPT`를 교체:

```python
SYSTEM_PROMPT = """너는 한국어 블로그 포스트의 문체 분석가다.
제공된 샘플 포스트에서 재사용 가능한 안정적인 문체 특성을 추출해라.
포스트 내용을 요약하지 말고, 같은 문체로 다시 쓸 때 도움이 되는 반복 패턴에 집중해라.

샘플의 [사진]·[이미지]·[짤방]·[이모티콘:설명] 마커는 배치 빈도·스타일 신호로만 분석해라(내용 요약 금지).
특히 [짤방](반응용 밈/움짤)이 어떤 흐름·상황에서 등장하는지를 meme_usage_patterns로 정리해라.

다음 필드를 가진 JSON 객체만 반환해라:
{
  "structure_patterns": [...],
  "tone_keywords": [...],
  "frequent_expressions": [...],
  "review_conventions": [...],
  "photo_usage_notes": [...],
  "emoticon_usage_patterns": [...],
  "meme_usage_patterns": [...]
}

각 리스트는 3-8개의 간결한 한국어 문자열을 포함해야 한다. JSON 외의 다른 텍스트는 반환하지 마라."""
```

> `refresh_style_profile`의 본문 로직은 변경 불필요 — `StyleProfile(..., **data)`가 새 키를 자동 흡수한다. 모델이 키를 누락하면 기본값 []로 처리된다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_profile_refresh.py -q`
Expected: PASS (기존 `test_system_prompt_requests_emoticon_usage_patterns` 포함 — `emoticon_usage_patterns`/`[이모티콘` 문구 유지됨)

- [ ] **Step 5: 커밋**

```bash
git add src/naver_blog_bot/style_profiler/refresh.py tests/unit/test_profile_refresh.py
git commit -m "feat: refresh learns meme_usage_patterns + [짤방] marker (P3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: 대량 글 배치 map-reduce 빌드

**Files:**
- Modify: `src/naver_blog_bot/style_profiler/refresh.py` (배치 경로 추가)
- Test: `tests/unit/test_profile_refresh.py` (append)

소량(≤ batch_size)은 기존 단일 콜 그대로. 대량이면 chunk별 부분 프로필 추출 → 병합 콜로 통합.

- [ ] **Step 1: 실패하는 테스트 작성** — append:

```python
class RecordingCompleter:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls: list[str] = []

    def complete_text(self, *, system_prompt, user_prompt, cacheable_context=()):
        self.calls.append(user_prompt)
        return self._responses[len(self.calls) - 1]


def _axis_json(tag: str) -> str:
    return json.dumps(
        {
            "structure_patterns": [f"s-{tag}"],
            "tone_keywords": [f"t-{tag}"],
            "frequent_expressions": [f"e-{tag}"],
            "review_conventions": [f"r-{tag}"],
            "photo_usage_notes": [f"p-{tag}"],
            "emoticon_usage_patterns": [f"em-{tag}"],
            "meme_usage_patterns": [f"m-{tag}"],
        }
    )


def test_refresh_batches_large_corpus_then_merges() -> None:
    # 5 posts, batch_size=2 → 3 부분콜 + 1 병합콜 = 4 콜
    merged = _axis_json("MERGED")
    completer = RecordingCompleter([_axis_json("1"), _axis_json("2"), _axis_json("3"), merged])
    profile = refresh_style_profile(
        profile_name="flowerbend",
        blog_url="https://blog.naver.com/flowerbend",
        sample_texts=[f"포스트 {i}" for i in range(5)],
        completer=completer,
        batch_size=2,
    )
    assert len(completer.calls) == 4
    assert profile.tone_keywords == ["t-MERGED"]
    # 마지막 콜은 병합 콜(부분 JSON들을 입력으로 받음)
    assert "s-1" in completer.calls[-1] and "s-3" in completer.calls[-1]


def test_refresh_single_call_when_under_batch_size() -> None:
    completer = FakeCompleter(VALID_RESPONSE)
    refresh_style_profile(
        profile_name="default",
        blog_url="https://blog.naver.com/flowerbend",
        sample_texts=["a", "b"],
        completer=completer,
        batch_size=12,
    )
    # 단일 콜 경로 — last_system_prompt 가 분석 프롬프트
    assert "meme_usage_patterns" in completer.last_system_prompt
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_profile_refresh.py::test_refresh_batches_large_corpus_then_merges -q`
Expected: FAIL — `refresh_style_profile() got an unexpected keyword argument 'batch_size'`

- [ ] **Step 3: 구현** — `refresh.py`: 병합 프롬프트 상수 추가 + `refresh_style_profile`에 `batch_size` 파라미터와 배치 분기 추가:

```python
MERGE_PROMPT = """너는 여러 부분 문체 프로필(JSON)을 하나로 통합하는 편집자다.
같은 의미의 항목은 합치고 중복은 제거해, 블로그 전체를 대표하는 안정적 패턴만 남겨라.
입력과 동일한 7개 키를 가진 JSON 객체만 반환해라. 각 리스트는 3-8개. JSON 외 텍스트 금지.
키: structure_patterns, tone_keywords, frequent_expressions, review_conventions,
photo_usage_notes, emoticon_usage_patterns, meme_usage_patterns"""


def _complete_profile_json(completer: TextCompleter, system_prompt: str, user_prompt: str) -> dict:
    response = completer.complete_text(
        system_prompt=system_prompt, user_prompt=user_prompt, cacheable_context=()
    )
    try:
        data = json.loads(response)
    except json.JSONDecodeError as exc:
        raise ValueError("Claude returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Claude returned invalid JSON")
    return data


def refresh_style_profile(
    *,
    profile_name: str,
    blog_url: str,
    sample_texts: Sequence[str],
    completer: TextCompleter,
    batch_size: int = 12,
) -> StyleProfile:
    texts = list(sample_texts)
    if len(texts) <= batch_size:
        user_prompt = "샘플 블로그 포스트:\n\n" + "\n\n---\n\n".join(texts)
        data = _complete_profile_json(completer, SYSTEM_PROMPT, user_prompt)
    else:
        partials: list[str] = []
        for start in range(0, len(texts), batch_size):
            chunk = texts[start : start + batch_size]
            user_prompt = "샘플 블로그 포스트:\n\n" + "\n\n---\n\n".join(chunk)
            partial = completer.complete_text(
                system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, cacheable_context=()
            )
            partials.append(partial)
        merge_input = "부분 프로필들:\n\n" + "\n\n---\n\n".join(partials)
        data = _complete_profile_json(completer, MERGE_PROMPT, merge_input)
    try:
        return StyleProfile(profile_name=profile_name, blog_url=blog_url, **data)
    except Exception as exc:
        raise ValueError("Claude returned an invalid style profile") from exc
```

> 기존 단일-콜 테스트(`test_refresh_returns_...`, `test_refresh_raises_on_invalid_json` 등)는 sample_texts가 1-2개라 기본 batch_size=12 하에서 단일 콜 경로로 동일하게 동작한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_profile_refresh.py -q`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/naver_blog_bot/style_profiler/refresh.py tests/unit/test_profile_refresh.py
git commit -m "feat: batched map-reduce profile build for large corpora (P3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 11: `PostDocument.to_annotated_text` ([짤방]/[사진] 주석)

**Files:**
- Modify: `src/naver_blog_bot/blog_scraper/models.py`
- Test: `tests/unit/test_blog_scraper_models.py` (append)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/unit/test_blog_scraper_models.py` 끝에 추가:

```python
def test_to_annotated_text_marks_memes_and_photos() -> None:
    from naver_blog_bot.blog_scraper.models import (
        EmoticonBlock,
        ImageBlock,
        PostDocument,
        TextBlock,
    )

    doc = PostDocument(
        url="https://m.blog.naver.com/f/1",
        title="제목",
        blocks=[
            TextBlock(content="웃긴 일"),
            ImageBlock(alt="", src="https://cdn/meme.gif"),
            ImageBlock(alt="", src="https://cdn/photo.jpg"),
            EmoticonBlock(description="기쁨"),
        ],
    )
    text = doc.to_annotated_text({"https://cdn/meme.gif"})
    lines = text.splitlines()
    assert "[짤방]" in lines
    assert "[사진]" in lines
    assert "[이모티콘:기쁨]" in lines
    # meme 으로 표시된 src 만 [짤방]; 나머지 이미지는 [사진]
    assert text.count("[짤방]") == 1
    assert text.count("[사진]") == 1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_blog_scraper_models.py::test_to_annotated_text_marks_memes_and_photos -q`
Expected: FAIL — 메서드 없음

- [ ] **Step 3: 구현** — `blog_scraper/models.py`의 `PostDocument`에 메서드 추가(`to_structured_text` 아래, 기존 메서드는 변경 없음):

```python
    def to_annotated_text(self, meme_srcs: set[str]) -> str:
        lines: list[str] = []
        if self.title:
            lines += [f"제목: {self.title}", ""]
        for block in self.blocks:
            if block.type == "text":
                stripped = block.content.strip()
                if stripped:
                    lines.append(stripped)
            elif block.type == "image":
                lines.append("[짤방]" if block.src in meme_srcs else "[사진]")
            elif block.type == "emoticon":
                description = f":{block.description}" if block.description else ""
                lines.append(f"[이모티콘{description}]")
        return "\n".join(lines)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_blog_scraper_models.py -q`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/naver_blog_bot/blog_scraper/models.py tests/unit/test_blog_scraper_models.py
git commit -m "feat: PostDocument.to_annotated_text marks [짤방]/[사진] (P3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 12: CLI `profile-refresh` 짤방 통합 (`--all-categories`, `--no-memes`)

**Files:**
- Modify: `src/naver_blog_bot/cli.py` (`profile_refresh_command`)
- Test: `tests/unit/test_cli.py` (append)

먼저 현재 테스트 패턴 확인을 위해 `tests/unit/test_cli.py`를 읽고(기존 monkeypatch 방식) 동일 스타일로 작성한다.

동작:
- `--all-categories` ON → `scrape_blog_all(url)`로 전 글; OFF → 기존 `scrape(url, count)`.
- URL 소스가 하나라도 있고 `--no-memes` OFF → 스크랩 문서로 `harvest_memes(...)` 실행 → 자산을 `meme_index`에 `add_or_update_meme`로 병합 저장. harvest의 `meme_srcs`로 프로필 입력을 `to_annotated_text`로 생성.
- `--no-memes` ON 또는 URL 없음 → 기존 `to_structured_text` 입력.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/unit/test_cli.py`에 추가(기존 import/runner 패턴 재사용; 아래는 self-contained 형태):

```python
def test_profile_refresh_all_categories_harvests_memes(tmp_path, monkeypatch):
    import naver_blog_bot.cli as cli
    from naver_blog_bot.blog_scraper.models import ImageBlock, PostDocument, TextBlock
    from naver_blog_bot.meme_harvester.models import HarvestResult
    from naver_blog_bot.meme_library.models import MemeAsset
    from naver_blog_bot.style_profiler.models import StyleProfile
    from typer.testing import CliRunner

    monkeypatch.setenv("NAVER_BOT_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("NAVER_BOT_DRAFTS_DIR", str(tmp_path / "drafts"))
    monkeypatch.setenv("NAVER_BOT_MEMES_DIR", str(tmp_path / "memes"))
    monkeypatch.setenv("NAVER_BOT_BROWSER_PROFILE_DIR", str(tmp_path / "bp"))

    docs = [
        PostDocument(url="https://m.blog.naver.com/flowerbend/1", title="t", blocks=[
            TextBlock(content="본문"), ImageBlock(alt="", src="https://cdn/m.gif"),
        ])
    ]
    all_called = {}

    def fake_scrape_all(url, settings):
        all_called["url"] = url
        return docs

    def fake_harvest(documents, vision_client, *, memes_dir, cache_path, fetch=None):
        return HarvestResult(
            assets=[MemeAsset(id="harvested-abc", path=memes_dir / "harvested-abc.gif",
                              tags=["웃음"], use_cases=["유머"], alt_text="ㅋㅋ", frequency=3)],
            meme_srcs=["https://cdn/m.gif"],
        )

    captured = {}

    def fake_refresh(*, profile_name, blog_url, sample_texts, completer, batch_size=12):
        captured["sample_texts"] = list(sample_texts)
        return StyleProfile(profile_name=profile_name, blog_url=blog_url,
                            meme_usage_patterns=["반전 직후 짤방"])

    class FakeCompleter:
        def complete_text(self, **k):
            return "{}"

        def complete_vision(self, **k):
            return "{}"

    monkeypatch.setattr(cli, "scrape_source", lambda *a, **k: docs)
    monkeypatch.setattr(cli, "scrape_all", fake_scrape_all)
    monkeypatch.setattr(cli, "harvest_memes", fake_harvest)
    monkeypatch.setattr(cli, "refresh_style_profile", fake_refresh)
    monkeypatch.setattr(cli, "build_text_completer", lambda settings: FakeCompleter())

    runner = CliRunner()
    result = runner.invoke(cli.app, [
        "profile-refresh", "https://blog.naver.com/flowerbend",
        "--profile", "flowerbend", "--all-categories",
    ])
    assert result.exit_code == 0, result.output
    assert all_called["url"] == "https://blog.naver.com/flowerbend"
    # 짤방이 meme_index 에 등록됨
    from naver_blog_bot.meme_library.service import load_meme_index
    index = load_meme_index(tmp_path / "config" / "meme_index.json")
    assert any(m.id == "harvested-abc" for m in index.memes)
    # 프로필 입력이 [짤방] 주석 텍스트
    assert any("[짤방]" in t for t in captured["sample_texts"])


def test_profile_refresh_no_memes_skips_harvest(tmp_path, monkeypatch):
    import naver_blog_bot.cli as cli
    from naver_blog_bot.blog_scraper.models import ImageBlock, PostDocument, TextBlock
    from naver_blog_bot.style_profiler.models import StyleProfile
    from typer.testing import CliRunner

    monkeypatch.setenv("NAVER_BOT_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("NAVER_BOT_DRAFTS_DIR", str(tmp_path / "drafts"))
    monkeypatch.setenv("NAVER_BOT_MEMES_DIR", str(tmp_path / "memes"))
    monkeypatch.setenv("NAVER_BOT_BROWSER_PROFILE_DIR", str(tmp_path / "bp"))

    docs = [PostDocument(url="https://m.blog.naver.com/flowerbend/1", title="t",
                         blocks=[TextBlock(content="본문"), ImageBlock(alt="", src="https://cdn/m.gif")])]

    def boom(*a, **k):
        raise AssertionError("harvest must not run with --no-memes")

    monkeypatch.setattr(cli, "scrape_source", lambda *a, **k: docs)
    monkeypatch.setattr(cli, "harvest_memes", boom)
    monkeypatch.setattr(cli, "refresh_style_profile",
                        lambda **k: StyleProfile(profile_name=k["profile_name"], blog_url=k["blog_url"]))
    monkeypatch.setattr(cli, "build_text_completer", lambda settings: object())

    runner = CliRunner()
    result = runner.invoke(cli.app, [
        "profile-refresh", "https://blog.naver.com/flowerbend",
        "--profile", "flowerbend", "--no-memes",
    ])
    assert result.exit_code == 0, result.output
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_cli.py::test_profile_refresh_all_categories_harvests_memes -q`
Expected: FAIL — `--all-categories` 옵션 없음 / `scrape_all`·`harvest_memes` cli 미import

- [ ] **Step 3: 구현** — `cli.py` 수정.

상단 import 추가:

```python
from naver_blog_bot.blog_scraper.service import scrape as scrape_source
from naver_blog_bot.blog_scraper.service import scrape_all
from naver_blog_bot.meme_harvester.service import harvest_memes
```

> 기존에 이미 `from naver_blog_bot.blog_scraper.service import scrape as scrape_source`와 `meme_library.service`의 `add_or_update_meme/ensure_in_memes_dir/load_meme_index/save_meme_index/tag_meme_image` import가 있다. **새로 추가할 줄은 `scrape_all`과 `harvest_memes` 두 개뿐.** monkeypatch가 `cli.scrape_all`/`cli.harvest_memes`/`cli.refresh_style_profile`를 패치하므로 모듈 네임스페이스에 바인딩되어야 한다.

`profile_refresh_command` 시그니처에 옵션 2개 추가:

```python
    all_categories: Annotated[
        bool,
        typer.Option("--all-categories", help="전 카테고리·모든 글을 스크랩(종합 프로필)."),
    ] = False,
    no_memes: Annotated[
        bool,
        typer.Option("--no-memes", help="짤방 자동 수집 생략(스타일만 학습)."),
    ] = False,
```

본문에서 URL 소스 처리부를 다음과 같이 바꾼다. 기존 루프는 `sample_texts`/`url_examples`를 채운다. 여기에 (1) `--all-categories`면 `scrape_blog_all` 사용, (2) 스크랩된 문서를 모아 harvest, (3) harvest의 meme_srcs로 annotated text 생성을 추가한다. 핵심 변경(개념):

```python
    sample_texts: list[str] = []
    url_examples: list[ExamplePost] = []
    first_url: str | None = None
    scraped_docs: list = []  # PostDocument 누적 (짤방/주석용)

    for source in sources:
        if _is_url_source(source):
            if first_url is None:
                first_url = source
            try:
                if all_categories:
                    docs = scrape_all(source, settings)
                else:
                    docs = scrape_source(source, count, settings)
            except ValueError as exc:
                typer.echo(f"Error: {exc}")
                raise typer.Exit(1)
            if not docs:
                typer.echo(f"Error: no posts found at {source}")
                raise typer.Exit(1)
            scraped_docs.extend(docs)
            for doc in docs:
                url_examples.append(
                    ExamplePost(
                        title=doc.title or "",
                        url=doc.url,
                        structured_text=doc.to_structured_text(),
                    )
                )
        else:
            path = Path(source)
            if not path.is_file():
                typer.echo(f"Error: sample file not found: {source}")
                raise typer.Exit(1)
            sample_texts.append(path.read_text(encoding="utf-8"))

    # 짤방 수집 (URL 문서가 있고 opt-out 아닐 때)
    meme_srcs: set[str] = set()
    if scraped_docs and not no_memes:
        completer = build_text_completer(settings)
        if hasattr(completer, "complete_vision"):
            result = harvest_memes(
                scraped_docs,
                completer,
                memes_dir=settings.memes_dir,
                cache_path=settings.harvest_cache_path,
            )
            meme_srcs = set(result.meme_srcs)
            index = load_meme_index(settings.meme_index_path)
            for asset in result.assets:
                index = add_or_update_meme(index, asset)
            save_meme_index(settings.meme_index_path, index)
            typer.echo(f"Harvested memes: {len(result.assets)}")

    # URL 문서 텍스트를 (짤방 주석 포함) sample_texts 앞쪽에 추가
    for doc in scraped_docs:
        if meme_srcs:
            sample_texts.append(doc.to_annotated_text(meme_srcs))
        else:
            sample_texts.append(doc.to_structured_text())
```

이후 기존 `blog_url`/`refresh_style_profile`/저장 블록은 그대로 둔다. (단 `refresh_style_profile(...)`은 `completer=build_text_completer(settings)`를 다시 호출해도 무방하나, 위에서 만든 completer를 재사용하려면 변수 스코프를 함수 상단으로 올린다. 간단히 기존 호출 유지.)

> 주의: `add_or_update_meme`/`load_meme_index`/`save_meme_index`는 이미 cli.py에 import되어 있음(meme-add 등에서 사용). 중복 import 금지.

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_cli.py -q`
Expected: PASS (신규 2개 + 기존 전부)

- [ ] **Step 5: 회귀 + 커밋**

Run: `uv run pytest -q`
Expected: PASS

```bash
git add src/naver_blog_bot/cli.py tests/unit/test_cli.py
git commit -m "feat: profile-refresh harvests memes (--all-categories/--no-memes) (P3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase P4 — 매칭 통합 + 실데이터 검증

### Task 13: 생성기 후보 선별을 frequency 폴백으로 보강

**Files:**
- Modify: `src/naver_blog_bot/post_generator/generator.py` (`generate`의 후보 선별 한 줄)
- Test: `tests/unit/test_post_generator.py` (append)

`candidates_for_memo(memo)`가 비면(메모와 태그가 안 겹치면) `top_by_frequency`로 폴백해 항상 합리적 후보를 제공한다. 배치(2차 패스)는 그대로.

- [ ] **Step 1: 실패하는 테스트 작성** — append:

```python
def test_generate_falls_back_to_top_frequency_when_memo_no_match() -> None:
    fake = FakeClaude()
    now = datetime(2026, 6, 7, 12, 0, 0, tzinfo=timezone.utc)
    settings = Settings()
    generator = PostGenerator(settings=settings, claude_client=fake, now=lambda: now)
    style_profile = StyleProfile(blog_url="https://blog.naver.com/flowerbend")
    meme_index = MemeIndex(
        memes=[
            MemeAsset(id="popular", path=Path("a.png"), tags=["없음매칭"],
                      use_cases=["전혀안겹침"], alt_text="x", frequency=9),
            MemeAsset(id="rare", path=Path("b.png"), tags=["딴거"],
                      use_cases=["딴상황"], alt_text="y", frequency=1),
        ]
    )

    draft = generator.generate(
        photo_paths=[Path("p.jpg")],
        memo="메모에는 태그가 전혀 안 들어있음",
        style_profile=style_profile,
        meme_index=meme_index,
        use_vision=False,
    )
    # 후보 추천 섹션(첫 콜 user_prompt)에 popular 가 들어가야 함
    assert "popular" in fake.calls[0]["user_prompt"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/unit/test_post_generator.py::test_generate_falls_back_to_top_frequency_when_memo_no_match -q`
Expected: FAIL — 메모 매칭이 없어 후보 비어 `선택된 짤방 없음`만 들어감

- [ ] **Step 3: 구현** — `generator.py`의 `generate` 내 한 줄 교체:

```python
        selected_memes = (
            meme_index.candidates_for_memo(memo) or meme_index.top_by_frequency()
        )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_post_generator.py -q`
Expected: PASS (기존 `test_post_generator_builds_draft_with_cacheable_context`의 `selected_memes==[satisfied.png]`도 유지 — 메모 "만족" 매칭이 우선)

- [ ] **Step 5: 회귀 + 커밋**

Run: `uv run pytest -q`
Expected: PASS

```bash
git add src/naver_blog_bot/post_generator/generator.py tests/unit/test_post_generator.py
git commit -m "feat: meme candidate fallback to top_by_frequency (P4)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 14: 실데이터 검증 (goal-driven) — 컨트롤러 실행

> 이 태스크는 단위 테스트가 아니라 **실제 실행 검증**이다. 컨트롤러(메인 세션)가 직접 수행하고, 실패 시 원인 분석 후 해당 Phase 태스크로 되돌아간다. 비용·시간이 크므로 subagent에 위임하지 않는다.

**Files:**
- Create(임시, gitignored): `sim/verify_harvest.py`

- [ ] **Step 1: 전체 점검 통과 확인**

Run: `bash scripts/check.sh`
Expected: ruff check / format / pytest 모두 통과.

- [ ] **Step 2: 종합 프로필 + 짤방 수집 실제 실행**

Run(WSL, claude CLI 백엔드 사용):
```
uv run naver-bot profile-refresh https://blog.naver.com/flowerbend --profile flowerbend --all-categories
```
Expected: `Harvested memes: N` (N≥1) 출력 + `Style profile saved: .../flowerbend.json`. 산출 확인:
- `config/style_profiles/flowerbend.json` 존재, `meme_usage_patterns` 비어있지 않음, 7축 모두 채워짐.
- `config/meme_index.json`에 `harvested-*` 자산 다수 등록(frequency 분포 존재).
- `assets/memes/harvested-*.{jpg,png,gif,webp}` 파일 존재.

> 한글이 들어가는 인자는 없음(URL·옵션·프로필 id 전부 ASCII)이라 wsl.exe 인자 깨짐 문제 없음.

- [ ] **Step 3: 샘플 드래프트가 진짜 짤방을 배치하는지 확인**

기존 사진/메모로 드래프트 생성 후 본문에 `[짤방: harvested-...]` 마커가 들어가는지 확인:
```
uv run naver-bot draft <사진경로...> "<메모>" --profile flowerbend
uv run naver-bot preview <draft-id>
```
Expected: 생성된 `drafts/<id>.md`(body)에 최소 1개 이상의 `[짤방: harvested-...]` 마커가 흐름에 맞는 위치(놀람/웃음/감동 등)에 존재. 일반 이모지(`meme_smile` 등)가 아닌 수집된 자산이 우선 사용됨.

성공 기준(spec §목표) 충족 시 완료. 미달 시:
- 짤방이 0개 → P2 분류 게이트/다운로드(403) 점검(`config/.harvest-cache.json` 확인).
- 프로필 `meme_usage_patterns` 빈약 → P3 주석/프롬프트 점검.

- [ ] **Step 4: 임시 검증물 정리**

`sim/`는 gitignored이므로 커밋 불필요. 커밋할 코드 변경 없음.

---

## 클로즈아웃 (플랜 외 — 모든 태스크 후)

- 최종 코드 리뷰(subagent-driven-development의 final reviewer) → `superpowers:finishing-a-development-branch`.
- ADR-011 작성 → `docs/ai-context/architecture.md` append (신규 모듈 `meme_harvester`, 스크래퍼 이미지 URL 보존, 프로필 7축+배치, profile-refresh 데이터흐름 변경).
- `docs/ai-context/domain-glossary.md`: "짤방" 자동 수집 경로 + "flowerbend/이방봉 종합 프로필" 용어.
- `CLAUDE.md` Modules에 `meme_harvester` 한 줄 추가(**세션 종료 직전** — §1 캐시 안정성).
- non-obvious 후보 발견 시 §4 절차로 등록 검토.
```
