# Naver Post-Body Fixture Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** completed
**RPI-Cycle:** 15
**Started:** 2026-06-07

**Goal:** Add recorded realistic-HTML fixture-based characterization tests for the Naver adapter's POST-BODY parse path (`parse_post_html` and helpers) so Naver SmartEditor-ONE / legacy response-shape drift is caught early.

**Architecture:** The target parsers (`parse_post_html`, `_parse_se_main_container`, `_classify_se_component`, `_parse_legacy_area`, `_img_block_from_node`, `is_emoticon_img_attrs`) are pure functions over a parsed `HtmlNode` tree — no network, Playwright, or file I/O (explore-strict + Gate R confirmed). So this is **characterization testing**: realistic recorded HTML fixtures pin the *existing* behavior. **Zero source change.** Distinct value over the existing flat synthetic inline tests (`tests/unit/test_blog_scraper_naver.py`): deep `se-component > se-component-content > se-module > p > span` nesting, multi-`<p>` text collapse, non-`se-component` sibling skipping, empty components → `[]`, OGQ/sticker URL-pattern detection through `se-image` (vs `se-sticker` component-class), and nested legacy `#postViewArea` walking — none of which the flat snippets exercise.

**Tech Stack:** Python 3.11+, pytest, stdlib `pathlib`. Fixtures are static `.html` files under `tests/unit/fixtures/naver/`, loaded with `Path(...).read_text(encoding="utf-8")` (mirrors cycle-14 `test_blog_scraper_naver_fixtures.py`).

**Spec:** `docs/superpowers/specs/2026-05-07-blog-scraper-design.md` §13 (blog_scraper/adapters/naver.py test list) — spec delta NO-OP (these tests are already mandated). **ADR:** none (test-only).

**Characterization note:** Because the parser already works, each test encodes the *expected current* behavior. Red→green here = "fixture file missing → FileNotFoundError" (red) then "fixture added → test passes" (green). A test that fails *after* its fixture exists means either the expected-value trace is wrong or a real regression — investigate, do not blindly edit the assertion.

---

## File Structure

- Create: `tests/unit/fixtures/naver/post_smarteditor.html` — realistic SmartEditor ONE `.se-main-container` post body.
- Create: `tests/unit/fixtures/naver/post_smarteditor_empty.html` — container present but zero extractable blocks.
- Create: `tests/unit/fixtures/naver/post_legacy.html` — legacy `#postViewArea` post body.
- Create: `tests/unit/fixtures/naver/post_unsupported.html` — realistic deleted/private-post page (no known container).
- Modify: `tests/unit/test_blog_scraper_naver_fixtures.py` — add post-body imports + 6 characterization tests (extends the cycle-14 URL-collection module).

No source files are touched.

---

### Task 1: SmartEditor ONE post-body fixtures + tests

**Files:**
- Create: `tests/unit/fixtures/naver/post_smarteditor.html`
- Create: `tests/unit/fixtures/naver/post_smarteditor_empty.html`
- Modify: `tests/unit/test_blog_scraper_naver_fixtures.py`

- [x] **Step 1: Add post-body imports to the test module**

At the top of `tests/unit/test_blog_scraper_naver_fixtures.py`, the existing imports are:
```python
import json
from pathlib import Path

import pytest

from naver_blog_bot.blog_scraper.adapters import naver
from naver_blog_bot.blog_scraper.adapters.html import parse_html, select_all
```
Add the post-body parse entry point and the block models. After the existing `from naver_blog_bot.blog_scraper.adapters import naver` block, the import section becomes:
```python
import json
from pathlib import Path

import pytest

from naver_blog_bot.blog_scraper.adapters import naver
from naver_blog_bot.blog_scraper.adapters.html import parse_html, select_all
from naver_blog_bot.blog_scraper.adapters.naver import parse_post_html
from naver_blog_bot.blog_scraper.models import EmoticonBlock, ImageBlock, TextBlock
```
(`_load` helper already exists in the file and is reused for HTML fixtures.)

- [x] **Step 2: Write the failing SmartEditor body tests**

Append to `tests/unit/test_blog_scraper_naver_fixtures.py`:
```python
# --- SmartEditor ONE post body (parse_post_html .se-main-container path) ---


def test_post_smarteditor_fixture_block_order_and_classification() -> None:
    doc = parse_post_html(
        _load("post_smarteditor.html"), "https://m.blog.naver.com/flowerbend/223456789"
    )
    assert doc.title == "플라워벤드 봄 신상 원피스 솔직 후기"
    assert [type(b) for b in doc.blocks] == [
        TextBlock,
        ImageBlock,
        EmoticonBlock,
        TextBlock,
        EmoticonBlock,
    ]
    assert doc.blocks[1].alt == "민트색 원피스 정면 컷"
    assert doc.blocks[3].content == "색감이 화면보다 실물이 훨씬 예뻐요!"


def test_post_smarteditor_fixture_collapses_multiparagraph_text() -> None:
    doc = parse_post_html(
        _load("post_smarteditor.html"), "https://m.blog.naver.com/flowerbend/223456789"
    )
    # Two <p> inside one se-text component collapse to ONE whitespace-joined TextBlock.
    assert doc.blocks[0].content == (
        "안녕하세요, 플라워벤드입니다. 오늘은 봄 신상 원피스를 소개할게요."
    )


def test_post_smarteditor_fixture_detects_emoticons_two_ways() -> None:
    doc = parse_post_html(
        _load("post_smarteditor.html"), "https://m.blog.naver.com/flowerbend/223456789"
    )
    # blocks[2]: se-sticker COMPONENT class -> emoticon (src is an OGQ CDN url that
    # does NOT match the URL patterns, so only the component-class path catches it).
    assert isinstance(doc.blocks[2], EmoticonBlock)
    assert doc.blocks[2].description == "설레는 표정"
    # blocks[4]: se-image whose img src matches "static/se/sticker" URL pattern.
    assert isinstance(doc.blocks[4], EmoticonBlock)
    assert doc.blocks[4].description == "하트뿅뿅"


def test_post_smarteditor_empty_fixture_returns_no_blocks() -> None:
    doc = parse_post_html(
        _load("post_smarteditor_empty.html"),
        "https://m.blog.naver.com/flowerbend/1",
    )
    # Container present, but only an empty se-text + a non-se-component sibling:
    # graceful empty block list, NOT a crash.
    assert doc.title == "빈 본문 테스트"
    assert doc.blocks == []
```

- [x] **Step 3: Run the new tests to verify they fail (fixtures missing)**

Run:
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'cd /home/indietogo/projects/naver-blog-bot && export PATH="/home/indietogo/.local/bin:$PATH" && uv run pytest tests/unit/test_blog_scraper_naver_fixtures.py -q -k post_smarteditor'
```
Expected: FAIL with `FileNotFoundError` (post_smarteditor.html / post_smarteditor_empty.html do not exist yet).

- [x] **Step 4: Create `post_smarteditor.html`**

Create `tests/unit/fixtures/naver/post_smarteditor.html` with exactly:
```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>플라워벤드 봄 신상 원피스 솔직 후기 : 네이버 블로그</title>
</head>
<body>
<div id="post-area">
  <div class="se-main-container">

    <div class="se-component se-text se-l-default">
      <div class="se-component-content">
        <div class="se-module se-module-text">
          <p class="se-text-paragraph"><span class="se-fs16">안녕하세요, 플라워벤드입니다.</span></p>
          <p class="se-text-paragraph"><span class="se-fs16">오늘은 봄 신상 원피스를 소개할게요.</span></p>
        </div>
      </div>
    </div>

    <div class="se-component se-image se-l-default">
      <div class="se-component-content">
        <div class="se-module se-module-image">
          <a class="se-module-image-link" href="#">
            <img src="https://postfiles.pstatic.net/MjAyNjA2/dress_front.jpg?type=w773" alt="민트색 원피스 정면 컷" class="se-image-resource" data-lazy-src="https://postfiles.pstatic.net/MjAyNjA2/dress_front.jpg?type=w80">
          </a>
        </div>
      </div>
    </div>

    <div class="se-component se-sticker se-l-default">
      <div class="se-component-content">
        <div class="se-module se-module-sticker">
          <img src="https://storep-phinf.pstatic.net/ogq_5f0/original_30.png" alt="설레는 표정" class="se-sticker-image">
        </div>
      </div>
    </div>

    <div class="se-component se-text se-l-default">
      <div class="se-component-content">
        <div class="se-module se-module-text">
          <p class="se-text-paragraph">색감이 화면보다 실물이 훨씬 예뻐요!</p>
        </div>
      </div>
    </div>

    <div class="se-component se-text se-l-default">
      <div class="se-component-content">
        <div class="se-module se-module-text">
          <p class="se-text-paragraph"><br></p>
        </div>
      </div>
    </div>

    <div class="se-section-padding"></div>
    <script type="text/javascript">var ready = true;</script>

    <div class="se-component se-image se-l-default">
      <div class="se-component-content">
        <div class="se-module se-module-image">
          <img src="https://ssl.pstatic.net/static/se/sticker/heart_pop.png" alt="하트뿅뿅" class="se-image-resource">
        </div>
      </div>
    </div>

  </div>
</div>
</body>
</html>
```

Block-by-block trace (direct children of `.se-main-container`, processed by `_parse_se_main_container` → `_classify_se_component`):
1. se-text (two `<p>`) → `normalize_text(text_content)` collapses to one `TextBlock("안녕하세요, 플라워벤드입니다. 오늘은 봄 신상 원피스를 소개할게요.")`.
2. se-image (postfiles url, not emoticon) → `ImageBlock(alt="민트색 원피스 정면 컷")`.
3. se-sticker (component class) → `EmoticonBlock(description="설레는 표정")` from first img alt.
4. se-text → `TextBlock("색감이 화면보다 실물이 훨씬 예뻐요!")`.
5. se-text empty (`<br>` only) → `normalize_text` is empty → no block.
6. `se-section-padding` div + `<script>` → no `se-component` class → skipped.
7. se-image (`static/se/sticker` url matches `is_emoticon_img_attrs`) → `EmoticonBlock(description="하트뿅뿅")`.

- [x] **Step 5: Create `post_smarteditor_empty.html`**

Create `tests/unit/fixtures/naver/post_smarteditor_empty.html` with exactly:
```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>빈 본문 테스트 : 네이버 블로그</title>
</head>
<body>
<div class="se-main-container">
  <div class="se-component se-text se-l-default">
    <div class="se-component-content">
      <div class="se-module se-module-text"><p class="se-text-paragraph"><br></p></div>
    </div>
  </div>
  <div class="se-section-padding"></div>
</div>
</body>
</html>
```
Trace: container found → empty se-text → `[]`; `se-section-padding` non-component → skipped. `doc.blocks == []`, `doc.title == "빈 본문 테스트"`.

- [x] **Step 6: Run the SmartEditor tests to verify they pass**

Run:
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'cd /home/indietogo/projects/naver-blog-bot && export PATH="/home/indietogo/.local/bin:$PATH" && uv run pytest tests/unit/test_blog_scraper_naver_fixtures.py -q -k post_smarteditor'
```
Expected: PASS (4 tests).

- [x] **Step 7: Commit**

```bash
wsl -d Ubuntu-24.04 -- bash -lc 'cd /home/indietogo/projects/naver-blog-bot && bash scripts/git-commit.sh -m "test: add SmartEditor ONE post-body characterization fixtures (cycle 15)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"'
```

---

### Task 2: Legacy + unsupported post-body fixtures + tests

**Files:**
- Create: `tests/unit/fixtures/naver/post_legacy.html`
- Create: `tests/unit/fixtures/naver/post_unsupported.html`
- Modify: `tests/unit/test_blog_scraper_naver_fixtures.py`

- [x] **Step 1: Write the failing legacy + unsupported tests**

Append to `tests/unit/test_blog_scraper_naver_fixtures.py`:
```python
# --- Legacy #postViewArea body + unsupported structure ---


def test_post_legacy_fixture_block_order_and_classification() -> None:
    doc = parse_post_html(
        _load("post_legacy.html"), "https://m.blog.naver.com/flowerbend/1"
    )
    assert doc.title == "2019년 가을 제주 여행 기록"
    assert [type(b) for b in doc.blocks] == [
        TextBlock,
        ImageBlock,
        TextBlock,
        ImageBlock,
        EmoticonBlock,
        TextBlock,
    ]
    assert doc.blocks[0].content == "제주도에 다녀왔습니다."
    assert doc.blocks[1].alt == "제주 바다"
    assert doc.blocks[3].alt == "제주 카페"
    assert doc.blocks[4].description == "신난 표정"
    assert doc.blocks[5].content == "다음에 또 가고 싶어요."


def test_post_unsupported_fixture_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="unsupported Naver post structure"):
        parse_post_html(
            _load("post_unsupported.html"), "https://m.blog.naver.com/flowerbend/1"
        )
```

- [x] **Step 2: Run to verify failure (fixtures missing)**

Run:
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'cd /home/indietogo/projects/naver-blog-bot && export PATH="/home/indietogo/.local/bin:$PATH" && uv run pytest tests/unit/test_blog_scraper_naver_fixtures.py -q -k "post_legacy or post_unsupported"'
```
Expected: FAIL with `FileNotFoundError`.

- [x] **Step 3: Create `post_legacy.html`**

Create `tests/unit/fixtures/naver/post_legacy.html` with exactly:
```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>2019년 가을 제주 여행 기록 - 네이버 블로그</title>
</head>
<body>
<div id="post-view">
  <div id="postViewArea">
    <p><span style="font-size: 16px;">제주도에 다녀왔습니다.</span></p>
    <img src="https://blogfiles.pstatic.net/MjAxOQ/jeju_sea.jpg" alt="제주 바다">
    <p>날씨가 정말 좋았어요.</p>
    <div>
      <img src="https://mblogthumb-phinf.pstatic.net/photo/jeju_cafe.jpg" alt="제주 카페">
    </div>
    <p><img src="https://ssl.pstatic.net/static/se/emoticon/happy.png" alt="신난 표정" class="_sticker"></p>
    <p>다음에 또 가고 싶어요.</p>
  </div>
</div>
</body>
</html>
```

Trace (`_parse_legacy_area._walk` over `#postViewArea` direct children; `p`/`div`/`span`/`br` take their whole `text_content` then descendant imgs):
1. `<p><span>...</span></p>` → `TextBlock("제주도에 다녀왔습니다.")`.
2. direct `<img>` (blogfiles, not emoticon) → `ImageBlock(alt="제주 바다")`.
3. `<p>날씨가 정말 좋았어요.</p>` → `TextBlock("날씨가 정말 좋았어요.")`.
4. `<div><img></div>` → div text empty (no TextBlock) + descendant img (mblogthumb, not emoticon) → `ImageBlock(alt="제주 카페")`.
5. `<p><img static/se/emoticon ...></p>` → p text empty + img src matches `static/se/emoticon` → `EmoticonBlock(description="신난 표정")`.
6. `<p>다음에 또 가고 싶어요.</p>` → `TextBlock("다음에 또 가고 싶어요.")`.

- [x] **Step 4: Create `post_unsupported.html`**

Create `tests/unit/fixtures/naver/post_unsupported.html` with exactly:
```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>네이버 블로그</title>
</head>
<body>
<div class="error_wrap">
  <div class="error_content">
    <h2>존재하지 않거나 삭제된 게시글입니다.</h2>
    <p>해당 게시물이 비공개 상태이거나 삭제되었을 수 있습니다.</p>
  </div>
</div>
</body>
</html>
```
Trace: no `.se-main-container`, no `#postViewArea` → `raise ValueError("unsupported Naver post structure")`.

- [x] **Step 5: Run the legacy + unsupported tests to verify they pass**

Run:
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'cd /home/indietogo/projects/naver-blog-bot && export PATH="/home/indietogo/.local/bin:$PATH" && uv run pytest tests/unit/test_blog_scraper_naver_fixtures.py -q -k "post_legacy or post_unsupported"'
```
Expected: PASS (2 tests).

- [x] **Step 6: Commit**

```bash
wsl -d Ubuntu-24.04 -- bash -lc 'cd /home/indietogo/projects/naver-blog-bot && bash scripts/git-commit.sh -m "test: add legacy #postViewArea + unsupported-structure post-body fixtures (cycle 15)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"'
```

---

### Task 3: Full verification gate

**Files:** none (verification only).

- [x] **Step 1: Run the full new fixture module**

Run:
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'cd /home/indietogo/projects/naver-blog-bot && export PATH="/home/indietogo/.local/bin:$PATH" && uv run pytest tests/unit/test_blog_scraper_naver_fixtures.py -q'
```
Expected: PASS (cycle-14's 8 URL tests + cycle-15's 6 body tests = 14 passed).

- [x] **Step 2: Run the full quality gate and confirm RC 0 (NOBV-002)**

Run (do NOT trust the displayed RC through the WSL boundary — branch on exit status + confirm the "passed" token + the completion marker):
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'cd /home/indietogo/projects/naver-blog-bot && export PATH="/home/indietogo/.local/bin:$PATH" && if bash scripts/check.sh > /tmp/check15.log 2>&1; then echo CHECK_EXIT_OK; else echo CHECK_EXIT_FAIL; fi; tail -n 6 /tmp/check15.log'
```
Expected: `CHECK_EXIT_OK`, `ruff check` clean, `ruff format --check` clean, `185 passed` (179 prior + 6 new), `== check complete ==`.

- [x] **Step 3: Confirm no source files changed (characterization invariant)**

Run:
```bash
wsl -d Ubuntu-24.04 -- bash -lc 'cd /home/indietogo/projects/naver-blog-bot && git diff --name-only HEAD~2 -- src/ | cat; echo "---END---"'
```
Expected: empty list before `---END---` (only `tests/` changed across the two task commits). If any `src/` file appears, a non-characterization change leaked — investigate.

---

## Self-Review

- **Spec coverage:** §13 naver body-parse items — `.se-main-container/.se-component → block list` (Task 1), `OGQ URL → EmoticonBlock` (Task 1 blocks[4], Task 2 blocks[4]), `regular img → ImageBlock` (Task 1 blocks[1], Task 2 blocks[1,3]), `text paragraph → TextBlock` (both), `legacy #postViewArea fallback → block list` (Task 2). All covered.
- **Placeholder scan:** none — every fixture and test is given verbatim with traced expected values.
- **Type consistency:** tests import `parse_post_html`, `TextBlock`, `ImageBlock`, `EmoticonBlock` (exact names from `models.py` / `naver.py`). `_load` reused from the existing module. Block attribute names (`.content`, `.alt`, `.description`) match `models.py`.
- **Characterization invariant:** zero `src/` change (Task 3 Step 3 enforces). New tests pin existing behavior; richer shapes catch shape-drift the flat inline synthetic tests do not.

---

## Execution Result (2026-06-07)

- **Task 1** (commit `6d35ceb`): `post_smarteditor.html` + `post_smarteditor_empty.html` + 4 tests + this plan. RED confirmed (FileNotFoundError on missing fixtures) → GREEN (4 passed).
- **Task 2** (commit `9c01535`): `post_legacy.html` + `post_unsupported.html` + 2 tests. RED (FileNotFoundError) → GREEN (2 passed).
- **Task 3** (verification): full fixture module **14 passed** (8 cycle-14 + 6 cycle-15); `bash scripts/check.sh` **CHECK_EXIT_OK / 185 passed / == check complete ==** (RC 0 via exit-branch + passed token + marker, NOBV-002 — displayed RC unreliable through WSL boundary); `git diff --name-only HEAD~2 -- src/` **empty** (characterization invariant: 0 source change).
- All 6 success criteria met. spec delta NO-OP; no ADR; no new domain terms.

