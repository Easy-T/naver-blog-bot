# Blog Scraper Design Spec

Created: 2026-05-07
Project: naver-blog-bot
Cycle: blog-scraper

## 1. Goal

Extend `naver-bot profile-refresh` to accept blog post URLs in addition to local files. The scraper extracts text, image positions, and emoticon positions as an ordered block sequence, preserving the structural rhythm (text → image → emoticon → text) that defines a blogger's writing style.

The extracted structure feeds the existing Claude-based style extraction pipeline, which learns patterns like "감탄 이모티콘이 이미지 2장 뒤에 등장" and stores them in `StyleProfile.emoticon_usage_patterns`.

## 2. Scope

Supported in this slice:

- `naver-bot profile-refresh [--profile <name>] [--count N] <url-or-file...>`
- URL scraping for Naver Blog (`blog.naver.com`, `m.blog.naver.com`)
- URL scraping for Tistory (`*.tistory.com`)
- Generic fallback for other public blog URLs
- Reuse of existing `browser-profile-dir` Playwright session for Naver (own blog login)
- `blog_scraper` module: `models.py`, `service.py`, `adapters/`
- `StyleProfile.emoticon_usage_patterns` field addition
- Updated `refresh.py` SYSTEM_PROMPT to recognize `[이미지]` and `[이모티콘]` markers
- Updated `PostGenerator` draft prompt to apply emoticon usage patterns
- `{{이모티콘:감정유형}}` marker convention in `body_markdown`
- Polite scraping: 1-second delay between requests

Out of scope for this slice:

- Private post access (login-gated content beyond existing browser session)
- Downloading or storing actual emoticon image files
- Scraping platforms other than Naver Blog, Tistory, and generic HTML
- Rate limit detection or retry logic
- Caching scraped content to disk
- Profile listing, deletion, or rename commands

## 3. User Workflow

### Scrape own Naver Blog (5 most recent posts, default profile)

```bash
naver-bot profile-refresh https://blog.naver.com/myid
```

Scrapes 5 most recent public posts, extracts style, writes `config/style_profiles/default.json`.

### Scrape a specific post count

```bash
naver-bot profile-refresh --count 10 https://blog.naver.com/myid
```

### Scrape a Tistory blog and a local file together

```bash
naver-bot profile-refresh --profile food-review \
  https://myblog.tistory.com \
  samples/extra_post.md
```

URLs and local files can be mixed freely in a single command.

### Scrape a single post URL

```bash
naver-bot profile-refresh https://blog.naver.com/myid/223456789
```

Single post URL → scrapes exactly that post (ignores `--count`).

## 4. Module Structure

```
src/naver_blog_bot/
└── blog_scraper/
    ├── __init__.py
    ├── models.py        # PostDocument, TextBlock, ImageBlock, EmoticonBlock
    ├── service.py       # URL detection, platform routing, Playwright lifecycle
    └── adapters/
        ├── __init__.py
        ├── naver.py     # Naver Blog (mobile URL + SmartEditor DOM parsing)
        ├── tistory.py   # Tistory (standard HTML)
        └── generic.py   # Fallback for any other public blog
```

## 5. Data Model

### Block types

```python
from typing import Literal
from pydantic import BaseModel

class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    content: str

class ImageBlock(BaseModel):
    type: Literal["image"] = "image"
    alt: str = ""

class EmoticonBlock(BaseModel):
    type: Literal["emoticon"] = "emoticon"
    description: str = ""  # inferred from alt text, e.g. "만족하는 표정"
```

### PostDocument

```python
PostBlock = TextBlock | ImageBlock | EmoticonBlock

class PostDocument(BaseModel):
    url: str
    title: str = ""
    blocks: list[PostBlock]

    def to_structured_text(self) -> str:
        lines: list[str] = []
        if self.title:
            lines += [f"제목: {self.title}", ""]
        for block in self.blocks:
            if block.type == "text":
                stripped = block.content.strip()
                if stripped:
                    lines.append(stripped)
            elif block.type == "image":
                lines.append("[이미지]")
            elif block.type == "emoticon":
                desc = f":{block.description}" if block.description else ""
                lines.append(f"[이모티콘{desc}]")
        return "\n".join(lines)
```

Example output of `to_structured_text()`:

```
제목: 포포몬 첫 사용 후기

오늘 드디어 써봤는데요.
[이미지]
첫인상은 생각보다 훨씬 좋았어요!
[이모티콘:만족하는 표정]
전반적으로 추천합니다.
[이미지]
[이미지]
[이모티콘:엄지척]
```

This preserves the positional rhythm of text, images, and emoticons in document order.

## 6. Emoticon Detection Strategy

SmartEditor ONE's CSS class names are proprietary and may change. Use URL pattern matching as the primary strategy, with CSS class matching as secondary.

```python
EMOTICON_URL_PATTERNS = [
    "ogq.me",
    "pstatic.net/static/se/sticker",
    "pstatic.net/static/se/emoticon",
]

EMOTICON_CSS_KEYWORDS = ["emoticon", "sticker"]

def is_emoticon_img(img_tag) -> bool:
    src = img_tag.get("src", "") or ""
    classes = " ".join(img_tag.get("class") or []).lower()
    return (
        any(p in src for p in EMOTICON_URL_PATTERNS)
        or any(k in classes for k in EMOTICON_CSS_KEYWORDS)
    )
```

## 7. Platform Adapters

### URL detection (service.py)

```python
from urllib.parse import urlparse

def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "blog.naver.com" in host or "m.blog.naver.com" in host:
        return "naver"
    if host.endswith(".tistory.com"):
        return "tistory"
    return "generic"
```

### Naver adapter

**URL normalisation:** Convert PC blog URL to mobile to avoid iframe complexity.

```
https://blog.naver.com/myid           → https://m.blog.naver.com/myid
https://blog.naver.com/myid/223456789 → https://m.blog.naver.com/myid/223456789
```

**Blog URL vs post URL:** If the path has no post number (e.g. `/myid`), navigate to the post list page and collect up to `count` post URLs before scraping.

**Post list URL:** `https://m.blog.naver.com/PostList.naver?blogId=<id>&currentPage=1`

**Content extraction (SmartEditor ONE):**

Primary selector: `.se-main-container`

Iterate child elements in DOM order. For each `.se-component`:
- Contains `.se-text` → TextBlock (extract inner text)
- Contains `img` matched by `is_emoticon_img()` → EmoticonBlock
- Contains `img` not matched → ImageBlock

Fallback selector if `.se-main-container` not found: `#postViewArea` (legacy SmartEditor 2.0), apply same block classification on child elements.

**Session reuse:** Launch Playwright with `user_data_dir=settings.browser_profile_dir` so the existing Naver login session is reused.

### Tistory adapter

Content selectors (try in order):
1. `article.entry-content`
2. `.tt_article_useless_p_margin`
3. `.article_view`
4. `#content`

Block classification:
- `<p>` with non-empty text → TextBlock
- `<img>` → ImageBlock (Tistory does not use OGQ emoticons)
- No EmoticonBlock for Tistory

Post list URL for blog-level scraping: `https://<blog>.tistory.com` → collect `<a>` links matching `/\d+$` pattern up to `count`.

### Generic adapter

Try selectors in order: `article`, `main`, `.content`, `#content`, `body`.

Block classification: same as Tistory (text paragraphs + images, no emoticons).

## 8. Scraper Service

```python
async def scrape_post(url: str, settings: Settings) -> PostDocument:
    """Scrape a single post URL and return a PostDocument."""

async def scrape_blog(
    url: str, count: int, settings: Settings
) -> list[PostDocument]:
    """Collect up to count post URLs from a blog index and scrape each."""

def scrape(
    url: str, count: int, settings: Settings
) -> list[PostDocument]:
    """Sync entry point. Detect blog vs post URL, run async scraper."""
```

Polite delay: 1-second `asyncio.sleep(1)` between consecutive post scrapes.

Playwright is launched once per `scrape()` call, shared across all posts in the batch, then closed.

## 9. profile-refresh CLI Extension

### Updated signature

```bash
naver-bot profile-refresh [--profile <name>] [--count N] <source...>
```

- `--count N`: integer, default 5, ignored for single post URLs and local files
- Each `<source>`: URL (starts with `http://` or `https://`) or local file path

### Behavior

1. Load settings, ensure directories.
2. Validate profile name.
3. Validate at least one source was provided.
4. For each source:
   - If URL → `blog_scraper.service.scrape(url, count, settings)` → list of PostDocuments → `doc.to_structured_text()` for each
   - If path → validate file exists → read UTF-8 text
5. Merge all texts into `sample_texts`.
6. Call `refresh_style_profile()`.
7. Save profile, print saved path and source count.

### Failure behavior

- URL scraping fails (network error, unsupported structure): print `Error: failed to scrape <url>: <reason>` and exit 1
- No posts found at blog URL: print `Error: no posts found at <url>` and exit 1
- All other failures: same as existing profile-refresh errors

## 10. StyleProfile Changes

Add one field:

```python
emoticon_usage_patterns: list[str] = Field(default_factory=list)
```

Keep all existing fields unchanged.

Example values Claude might extract:

```json
{
  "emoticon_usage_patterns": [
    "이미지 2장 뒤에 만족/감탄 계열 이모티콘",
    "포스트 마지막 문단 뒤에 마무리 이모티콘",
    "긍정적 경험 언급 직후 이모티콘"
  ]
}
```

## 11. SYSTEM_PROMPT Update (refresh.py)

Add to the existing system prompt:

```
샘플 텍스트에는 구조 마커가 포함될 수 있다:
- [이미지]: 실제 이미지 삽입 위치
- [이모티콘] 또는 [이모티콘:설명]: 이모티콘/스티커 삽입 위치

이 마커를 활용해 다음 필드도 추출해라:
"emoticon_usage_patterns": 이모티콘 삽입 빈도, 위치, 감정 유형의 반복 패턴
  (예: "이미지 뒤에 만족형 이모티콘", "포스트 마지막에 마무리 이모티콘 1개")
```

The JSON schema returned by Claude must include `emoticon_usage_patterns`.

## 12. PostGenerator Draft Changes

### Emoticon marker convention

Claude writes `{{이모티콘:감정유형}}` in `body_markdown` at emoticon insertion points:

```markdown
오늘 먹어본 음식은 정말 기대 이상이었어요.

{{이모티콘:만족/감탄}}

첫 입에 느껴지는 감칠맛이 일품이었는데요.
```

The publish step (future slice) replaces `{{이모티콘:감정유형}}` with an actual OGQ sticker chosen from the user's collection. Preview (`naver-bot preview`) shows the marker as-is so the user can read where emoticons are intended.

### PostGenerator prompt update

Add to the draft generation prompt:

```
이모티콘 사용 패턴: {style_profile.emoticon_usage_patterns}

포스트 본문에 이모티콘을 삽입할 위치는 {{이모티콘:감정유형}} 형식으로 표시해라.
감정유형은 한국어로 간단히 작성한다 (예: 만족, 감탄, 응원, 마무리).
이모티콘 위치는 학습된 패턴을 따라라.
```

## 13. Tests

### blog_scraper/models.py

- `to_structured_text()` produces correct marker format for each block type
- Empty text blocks are skipped
- Mixed block sequence produces correct ordered output

### blog_scraper/adapters/naver.py

- Fixture HTML with `.se-main-container` and `.se-component` children → correct block list
- Emoticon `img` with OGQ URL → EmoticonBlock
- Regular image `img` → ImageBlock
- Text paragraph → TextBlock
- Legacy `#postViewArea` fallback fixture → correct block list

### blog_scraper/adapters/tistory.py

- Fixture HTML with `article.entry-content` → correct block list (no EmoticonBlock)
- Post list page fixture → correct post URL extraction

### blog_scraper/adapters/generic.py

- Fixture HTML → correct block list using fallback selectors

### blog_scraper/service.py (monkeypatched Playwright)

- Blog URL routes to list scraping → calls adapter N times
- Single post URL routes directly → calls adapter once
- 1-second delay between posts (mock `asyncio.sleep` call count)

### style_profiler/models.py

- `StyleProfile` round-trip includes `emoticon_usage_patterns`
- Default value is empty list

### style_profiler/refresh.py

- FakeCompleter returning JSON with `emoticon_usage_patterns` → parsed into StyleProfile
- JSON missing `emoticon_usage_patterns` → defaults to empty list (backward compat)

### CLI profile-refresh (monkeypatched scraper)

- URL source → scraper called with correct url and count
- File source → file read, scraper not called
- Mixed URL + file → both processed
- `--count 10` passed to scraper
- Scrape failure → exit 1 with error message

### CLI draft (existing tests)

- Existing tests still pass (emoticon_usage_patterns defaults to empty list)

## 14. Architecture Impact

### New module

`blog_scraper` depends on: Playwright, `config.py`, `blog_scraper/models.py`.
`cli.py` imports `blog_scraper.service.scrape`.

### ADR

Add ADR-003 to `docs/ai-context/architecture.md`:
- Named: "Blog scraper uses mobile URL + URL-pattern-based emoticon detection"
- Reason: SmartEditor ONE CSS classes are proprietary; mobile URL avoids iframe complexity

### Glossary updates

- Add `블록 문서` / `PostDocument` with `to_structured_text()`
- Add `이모티콘 마커` / `{{이모티콘:감정유형}}` convention
- Update `스타일 프로필` to mention `emoticon_usage_patterns`

## 15. Self-Review

- **Scope check**: Scraping, model changes, prompt updates, and draft marker convention are all in scope. Downloading emoticon files and publish integration are deferred.
- **Chain completeness**: Scrape → PostDocument → structured text → SYSTEM_PROMPT → StyleProfile.emoticon_usage_patterns → PostGenerator prompt → `{{이모티콘}}` markers in draft. Full chain covered.
- **Stability**: Emoticon detection uses URL patterns as primary (stable CDN domains) rather than CSS classes (proprietary, may change).
- **Backward compat**: `emoticon_usage_patterns` defaults to empty list. Existing profiles without this field load without error. Existing draft tests unaffected.
- **Test coverage**: Each adapter tested with fixture HTML offline. CLI tested with monkeypatched scraper.
- **Ambiguity**: `--count` applies only to blog-level URLs. Single post URLs and local files always produce exactly one sample each.
