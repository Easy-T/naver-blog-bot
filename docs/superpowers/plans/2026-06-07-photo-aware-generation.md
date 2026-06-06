# Photo-Aware Draft Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `PostGenerator`가 각 사진을 vision으로 읽어 내용을 캡션하고, 그 캡션에 근거해 본문을 쓰고 사진을 이야기 흐름에 맞게 배치하도록 만든다 (기본 ON, `--no-vision` 폴백, 캡션 캐시).

**Architecture:** 신규 `photo_describer` 모듈이 사진을 EXIF 보정·다운스케일 후 vision 캡션(+content-hash 캐시)으로 변환한다. `PostGenerator.generate`는 vision ON일 때 캡션을 작성 프롬프트에 주입하고, OFF면 기존 경로-only 동작으로 폴백한다.

**Tech Stack:** Python 3.11, pydantic v2, Pillow, Typer, pytest. 기존 `shared.claude_client`(claude-code/anthropic-sdk 백엔드, 둘 다 `complete_vision` 보유) 재사용.

**성공 기준 (goal — 충족할 때까지 반복):**
1. vision ON `draft`에서 각 `[사진: path]`가 그 사진 실제 내용 텍스트와 인접.
2. 사진이 흐름(외관→입장→내부→제품→상담→착장→총평)에 맞게 재배치·그룹핑.
3. `--no-vision`이 기존 경로-only 동작 재현.
4. 동일 사진 재실행 시 vision 호출 0회(캐시).
5. EXIF 회전 사진도 올바르게 처리.
6. 기존 테스트 전부 + 신규 단위 테스트 통과, `scripts/check.sh` 통과.

---

## File Structure

- Create: `src/naver_blog_bot/photo_describer/__init__.py` — 패키지.
- Create: `src/naver_blog_bot/photo_describer/models.py` — `PhotoCaption` 모델.
- Create: `src/naver_blog_bot/photo_describer/service.py` — `describe_photos`, 캐시, 이미지 전처리, 캡션 파싱.
- Modify: `src/naver_blog_bot/config.py` — `caption_cache_path` 프로퍼티.
- Modify: `src/naver_blog_bot/post_generator/generator.py` — `generate(use_vision=True)`, 캡션 주입, SYSTEM_PROMPT 보강.
- Modify: `src/naver_blog_bot/cli.py` — `draft --no-vision`.
- Create: `tests/unit/test_photo_describer.py` — 신규 단위 테스트.
- Modify: `tests/unit/test_post_generator.py` — vision on/off 테스트 추가.
- Modify: `docs/ai-context/architecture.md` — ADR-010 append.
- Modify: `CLAUDE.md` — Modules에 `photo_describer` 한 줄(세션 종료 직전).

---

## Task 1: PhotoCaption 모델 + 패키지

**Files:**
- Create: `src/naver_blog_bot/photo_describer/__init__.py`
- Create: `src/naver_blog_bot/photo_describer/models.py`
- Test: `tests/unit/test_photo_describer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_photo_describer.py
from pathlib import Path

from naver_blog_bot.photo_describer.models import PhotoCaption


def test_photo_caption_defaults() -> None:
    c = PhotoCaption(path=Path("a.jpg"))
    assert c.path == Path("a.jpg")
    assert c.caption == ""
    assert c.category == "기타"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/naver-blog-bot && uv run pytest tests/unit/test_photo_describer.py -v`
Expected: FAIL (ModuleNotFoundError: photo_describer)

- [ ] **Step 3: Write minimal implementation**

```python
# src/naver_blog_bot/photo_describer/__init__.py
```

```python
# src/naver_blog_bot/photo_describer/models.py
from pathlib import Path

from pydantic import BaseModel


class PhotoCaption(BaseModel):
    path: Path
    caption: str = ""
    category: str = "기타"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_photo_describer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/naver_blog_bot/photo_describer tests/unit/test_photo_describer.py
git commit -m "feat(photo_describer): add PhotoCaption model"
```

---

## Task 2: 캡션 파싱 (`_parse_caption`)

**Files:**
- Modify: `src/naver_blog_bot/photo_describer/service.py` (create)
- Test: `tests/unit/test_photo_describer.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_photo_describer.py
from naver_blog_bot.photo_describer.service import _parse_caption


def test_parse_caption_json() -> None:
    c = _parse_caption(Path("x.jpg"), '{"caption": "파란 간판", "category": "외관"}')
    assert c.caption == "파란 간판"
    assert c.category == "외관"


def test_parse_caption_unknown_category_falls_back() -> None:
    c = _parse_caption(Path("x.jpg"), '{"caption": "뭔가", "category": "음식"}')
    assert c.category == "기타"


def test_parse_caption_plain_text_fallback() -> None:
    c = _parse_caption(Path("x.jpg"), "그냥 텍스트 설명")
    assert c.caption == "그냥 텍스트 설명"
    assert c.category == "기타"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_photo_describer.py -k parse_caption -v`
Expected: FAIL (cannot import _parse_caption)

- [ ] **Step 3: Write minimal implementation**

```python
# src/naver_blog_bot/photo_describer/service.py
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from naver_blog_bot.photo_describer.models import PhotoCaption
from naver_blog_bot.shared.protocols import VisionCompleter
from naver_blog_bot.storage.json_store import read_json, write_json

_CATEGORIES = ["외관", "내부", "제품", "원단", "상담", "측정", "인물", "기타"]
_MAX_DIM = 1024

VISION_PROMPT = (
    "이 사진을 한국어로 분석해 JSON만 반환해라.\n"
    '형식: {"caption": "...", "category": "..."}\n'
    "caption: 사진에 실제로 보이는 것을 1-2문장으로. 간판·화면 등 글자가 보이면 포함.\n"
    "category: 다음 중 하나 — 외관, 내부, 제품, 원단, 상담, 측정, 인물, 기타.\n"
    "JSON 외 텍스트는 절대 반환하지 마라."
)


def _parse_caption(path: Path, raw: str) -> PhotoCaption:
    text = (raw or "").strip()
    caption = text
    category = "기타"
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            caption = str(data.get("caption", "")).strip()
            category = str(data.get("category", "기타")).strip()
    except json.JSONDecodeError:
        pass
    if category not in _CATEGORIES:
        category = "기타"
    return PhotoCaption(path=path, caption=caption, category=category)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_photo_describer.py -k parse_caption -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/naver_blog_bot/photo_describer/service.py tests/unit/test_photo_describer.py
git commit -m "feat(photo_describer): parse vision caption JSON with category guard"
```

---

## Task 3: 이미지 전처리 (`_prepare_image`)

**Files:**
- Modify: `src/naver_blog_bot/photo_describer/service.py`
- Test: `tests/unit/test_photo_describer.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_photo_describer.py
from PIL import Image

from naver_blog_bot.photo_describer.service import _prepare_image


def _make_jpg(path: Path, size: tuple[int, int]) -> None:
    Image.new("RGB", size, (123, 200, 100)).save(path, "JPEG")


def test_prepare_image_downscales_large(tmp_path: Path) -> None:
    src = tmp_path / "big.jpg"
    _make_jpg(src, (3000, 2000))
    out = _prepare_image(src, tmp_path / "work")
    with Image.open(out) as im:
        assert max(im.size) <= 1024


def test_prepare_image_falls_back_on_bad_file(tmp_path: Path) -> None:
    bad = tmp_path / "notimage.jpg"
    bad.write_text("not an image", encoding="utf-8")
    out = _prepare_image(bad, tmp_path / "work")
    assert out == bad
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_photo_describer.py -k prepare_image -v`
Expected: FAIL (cannot import _prepare_image)

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/naver_blog_bot/photo_describer/service.py
def _prepare_image(path: Path, work_dir: Path) -> Path:
    """EXIF-orient + downscale into work_dir; return original path on any failure."""
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as im:
            oriented = ImageOps.exif_transpose(im)
            if max(oriented.size) > _MAX_DIM:
                oriented.thumbnail((_MAX_DIM, _MAX_DIM))
            rgb = oriented if oriented.mode == "RGB" else oriented.convert("RGB")
            work_dir.mkdir(parents=True, exist_ok=True)
            out = work_dir / f"{path.stem}.prep.jpg"
            rgb.save(out, "JPEG", quality=85)
            return out
    except Exception:
        return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_photo_describer.py -k prepare_image -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/naver_blog_bot/photo_describer/service.py tests/unit/test_photo_describer.py
git commit -m "feat(photo_describer): EXIF-orient + downscale images before vision"
```

---

## Task 4: `describe_photos` (캐시 + 폴백)

**Files:**
- Modify: `src/naver_blog_bot/photo_describer/service.py`
- Test: `tests/unit/test_photo_describer.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_photo_describer.py
from naver_blog_bot.photo_describer.service import describe_photos


class FakeVision:
    def __init__(self, reply: str = '{"caption": "설명", "category": "내부"}') -> None:
        self.reply = reply
        self.calls = 0

    def complete_vision(self, *, image_path: Path, prompt: str) -> str:
        self.calls += 1
        return self.reply


class BoomVision:
    def complete_vision(self, *, image_path: Path, prompt: str) -> str:
        raise RuntimeError("vision down")


def test_describe_photos_returns_captions(tmp_path: Path) -> None:
    src = tmp_path / "p.jpg"
    _make_jpg(src, (800, 600))
    fake = FakeVision()
    out = describe_photos([src], fake, cache_path=tmp_path / "cache.json")
    assert out[0].caption == "설명"
    assert out[0].category == "내부"
    assert fake.calls == 1


def test_describe_photos_uses_cache(tmp_path: Path) -> None:
    src = tmp_path / "p.jpg"
    _make_jpg(src, (800, 600))
    cache = tmp_path / "cache.json"
    first = FakeVision()
    describe_photos([src], first, cache_path=cache)
    second = FakeVision()
    out = describe_photos([src], second, cache_path=cache)
    assert second.calls == 0
    assert out[0].caption == "설명"


def test_describe_photos_falls_back_on_error(tmp_path: Path) -> None:
    src = tmp_path / "p.jpg"
    _make_jpg(src, (800, 600))
    out = describe_photos([src], BoomVision(), cache_path=tmp_path / "c.json")
    assert out[0].caption == ""
    assert out[0].category == "기타"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_photo_describer.py -k describe_photos -v`
Expected: FAIL (cannot import describe_photos)

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/naver_blog_bot/photo_describer/service.py
def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe_photos(
    paths: Sequence[Path],
    vision_client: VisionCompleter,
    *,
    cache_path: Path | None = None,
    work_dir: Path | None = None,
) -> list[PhotoCaption]:
    cache: dict = {}
    if cache_path is not None and cache_path.exists():
        try:
            cache = read_json(cache_path)
        except Exception:
            cache = {}
    if work_dir is None:
        base = cache_path.parent if cache_path is not None else Path(".")
        work_dir = base / ".caption-tmp"

    results: list[PhotoCaption] = []
    dirty = False
    for path in paths:
        try:
            key = _file_hash(path)
        except OSError:
            results.append(PhotoCaption(path=path))
            continue
        if key in cache:
            entry = cache[key]
            results.append(
                PhotoCaption(
                    path=path,
                    caption=entry.get("caption", ""),
                    category=entry.get("category", "기타"),
                )
            )
            continue
        prepared = _prepare_image(path, work_dir)
        try:
            raw = vision_client.complete_vision(image_path=prepared, prompt=VISION_PROMPT)
            cap = _parse_caption(path, raw)
        except Exception:
            cap = PhotoCaption(path=path)
        results.append(cap)
        cache[key] = {"caption": cap.caption, "category": cap.category}
        dirty = True

    if cache_path is not None and dirty:
        write_json(cache_path, cache)
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_photo_describer.py -v`
Expected: PASS (all photo_describer tests)

- [ ] **Step 5: Commit**

```bash
git add src/naver_blog_bot/photo_describer/service.py tests/unit/test_photo_describer.py
git commit -m "feat(photo_describer): describe_photos with content-hash cache + error fallback"
```

---

## Task 5: Settings.caption_cache_path

**Files:**
- Modify: `src/naver_blog_bot/config.py`
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_config.py
from naver_blog_bot.config import Settings


def test_caption_cache_path_under_drafts() -> None:
    s = Settings()
    assert s.caption_cache_path == s.drafts_dir / ".caption-cache.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_config.py -k caption_cache -v`
Expected: FAIL (AttributeError: caption_cache_path)

- [ ] **Step 3: Write minimal implementation**

```python
# add to Settings class in src/naver_blog_bot/config.py (next to other @property)
    @property
    def caption_cache_path(self) -> Path:
        return self.drafts_dir / ".caption-cache.json"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_config.py -k caption_cache -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/naver_blog_bot/config.py tests/unit/test_config.py
git commit -m "feat(config): add caption_cache_path under drafts dir"
```

---

## Task 6: PostGenerator vision 통합

**Files:**
- Modify: `src/naver_blog_bot/post_generator/generator.py`
- Test: `tests/unit/test_post_generator.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_post_generator.py
class FakeVisionClaude(FakeClaude):
    def __init__(self) -> None:
        super().__init__()
        self.vision_calls = 0

    def complete_vision(self, *, image_path, prompt) -> str:
        self.vision_calls += 1
        return '{"caption": "파란 MUTO TAILOR 간판", "category": "외관"}'


def _make_photo(p: Path) -> None:
    from PIL import Image

    Image.new("RGB", (640, 480), (10, 20, 30)).save(p, "JPEG")


def test_generate_uses_vision_captions_in_prompt(tmp_path: Path) -> None:
    photo = tmp_path / "26.jpg"
    _make_photo(photo)
    fake = FakeVisionClaude()
    now = datetime(2026, 6, 7, 12, 0, 0, tzinfo=timezone.utc)
    settings = Settings(drafts_dir=tmp_path / "drafts")
    generator = PostGenerator(settings=settings, claude_client=fake, now=lambda: now)

    generator.generate(
        photo_paths=[photo],
        memo="테일러샵 방문",
        style_profile=StyleProfile(blog_url="https://blog.naver.com/flowerbend"),
        meme_index=MemeIndex(),
    )

    assert fake.vision_calls == 1
    assert "파란 MUTO TAILOR 간판" in fake.calls[0]["user_prompt"]


def test_generate_no_vision_skips_vision(tmp_path: Path) -> None:
    photo = tmp_path / "26.jpg"
    _make_photo(photo)
    fake = FakeVisionClaude()
    now = datetime(2026, 6, 7, 12, 0, 0, tzinfo=timezone.utc)
    settings = Settings(drafts_dir=tmp_path / "drafts")
    generator = PostGenerator(settings=settings, claude_client=fake, now=lambda: now)

    generator.generate(
        photo_paths=[photo],
        memo="테일러샵 방문",
        style_profile=StyleProfile(blog_url="https://blog.naver.com/flowerbend"),
        meme_index=MemeIndex(),
        use_vision=False,
    )

    assert fake.vision_calls == 0
    assert str(photo) in fake.calls[0]["user_prompt"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_post_generator.py -k vision -v`
Expected: FAIL (generate() got unexpected keyword 'use_vision' / vision not called)

- [ ] **Step 3: Write minimal implementation**

Update SYSTEM_PROMPT (append one line, keep existing text):

```python
# src/naver_blog_bot/post_generator/generator.py — SYSTEM_PROMPT
SYSTEM_PROMPT = """너는 네이버 블로그 체험단 후기 초안을 작성하는 한국어 글쓰기 도우미다.
사용자의 기존 문체를 우선하고, 과장된 광고 문장보다 실제 사용 경험처럼 자연스럽게 쓴다.
사진 위치, 이모티콘 의도, 짤방 후보는 초안에 사람이 검토할 수 있는 표시로 남긴다.
이모티콘 위치는 캐시 컨텍스트의 emoticon_usage_patterns에서 학습한 패턴을 따른다. 모든 문단에 강제로 넣지 않는다.
사진 설명(내용·카테고리)이 주어지면 그 내용에 근거해 서술하고, 사진을 이야기 흐름에 맞게 재배치·그룹핑한다. 설명에 없는 내용을 지어내지 않는다."""
```

Add import + change generate + _build_user_prompt:

```python
# near other imports
from naver_blog_bot.photo_describer.models import PhotoCaption
from naver_blog_bot.photo_describer.service import describe_photos
```

```python
# generate() signature + body
    def generate(
        self,
        *,
        photo_paths: list[Path],
        memo: str,
        style_profile: StyleProfile,
        meme_index: MemeIndex,
        examples: list[ExamplePost] | None = None,
        use_vision: bool = True,
    ) -> Draft:
        captions: list[PhotoCaption] = []
        if use_vision and photo_paths and hasattr(self.claude_client, "complete_vision"):
            captions = describe_photos(
                photo_paths,
                self.claude_client,  # type: ignore[arg-type]
                cache_path=self.settings.caption_cache_path,
            )
        selected_memes = meme_index.candidates_for_memo(memo)
        body_markdown = self.claude_client.complete_text(
            system_prompt=SYSTEM_PROMPT,
            cacheable_context=[
                style_profile.to_cache_text(),
                meme_index.to_cache_text(),
            ],
            user_prompt=self._build_user_prompt(
                photo_paths, memo, selected_memes, examples, captions
            ),
        )
        body_markdown = self._place_memes_in_draft(body_markdown, meme_index)
        created_at = self.now()
        return Draft(
            id=draft_id_from_time(created_at),
            title=extract_title(body_markdown),
            memo=memo,
            body_markdown=body_markdown,
            photo_paths=photo_paths,
            selected_memes=[meme.path for meme in selected_memes],
            ogq_artwork_id=self.settings.ogq_artwork_id,
            created_at=created_at,
        )
```

```python
# _build_user_prompt signature + photo rendering
    def _build_user_prompt(
        self,
        photo_paths: list[Path],
        memo: str,
        selected_memes: list[MemeAsset],
        examples: list[ExamplePost] | None,
        captions: list[PhotoCaption] | None = None,
    ) -> str:
        caption_by_path = {str(c.path): c for c in (captions or [])}
        photo_lines: list[str] = []
        for path in photo_paths:
            cap = caption_by_path.get(str(path))
            if cap and cap.caption:
                photo_lines.append(f"- {path}: {cap.caption} [{cap.category}]")
            else:
                photo_lines.append(f"- {path}")
        photos = "\n".join(photo_lines)

        arrange_hint = (
            "\n사진은 위 설명을 참고해 이야기 흐름에 맞게 순서를 재배치하고 비슷한 사진은 묶어도 된다."
            if caption_by_path
            else ""
        )
```

Then in the returned f-string, change the `사진 경로:` block to include `{arrange_hint}` right after the `{photos}` list (keep everything else identical):

```python
        return f"""다음 메모와 사진 목록을 바탕으로 네이버 블로그 초안을 작성해줘.{examples_section}

메모:
{memo}

사진 경로:
{photos}{arrange_hint}

사용 가능한 OGQ 이모티콘:
- artworkId: {self.settings.ogq_artwork_id}
- name: {self.settings.ogq_name}

추천 짤방 후보:
{memes}

출력 형식:
- 첫 줄은 마크다운 H1 제목으로 작성
- 본문은 한국어 마크다운으로 작성
- 사진을 넣을 위치는 `[사진: 파일경로]` 형식으로 표시
- 이모티콘을 넣을 위치는 `{{{{이모티콘:감정유형}}}}` 형식으로 표시 (예: `{{{{이모티콘:만족}}}}`, `{{{{이모티콘:감탄}}}}`, `{{{{이모티콘:마무리}}}}`)
- 짤방을 넣을 위치는 `[짤방: meme_id]` 형식으로 표시
"""
```

- [ ] **Step 4: Run tests (new + regression)**

Run: `uv run pytest tests/unit/test_post_generator.py -v`
Expected: PASS (new vision tests + all existing tests still green)

- [ ] **Step 5: Commit**

```bash
git add src/naver_blog_bot/post_generator/generator.py tests/unit/test_post_generator.py
git commit -m "feat(post_generator): inject vision photo captions into draft generation"
```

---

## Task 7: CLI `--no-vision`

**Files:**
- Modify: `src/naver_blog_bot/cli.py` (draft_command, ~line 164-220)
- Test: `tests/unit/test_examples.py` 또는 기존 cli 테스트 위치 (없으면 회귀만)

- [ ] **Step 1: Add the flag + pass-through**

```python
# in draft_command signature, after profile option:
    no_vision: Annotated[
        bool,
        typer.Option("--no-vision", help="사진 vision 분석 생략 (빠른 경로-only 모드)."),
    ] = False,
```

```python
# in the generate(...) call inside draft_command, add the kwarg:
        draft = build_generator(settings).generate(
            photo_paths=photo_paths,
            memo=memo,
            style_profile=style_profile,
            meme_index=meme_index,
            examples=examples,
            use_vision=not no_vision,
        )
```

- [ ] **Step 2: Verify CLI help shows the flag**

Run: `uv run naver-bot draft --help`
Expected: `--no-vision` 옵션이 표시됨

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -q`
Expected: PASS (no regressions)

- [ ] **Step 4: Commit**

```bash
git add src/naver_blog_bot/cli.py
git commit -m "feat(cli): add draft --no-vision flag (vision on by default)"
```

---

## Task 8: 문서 — ADR-010 + CLAUDE.md

**Files:**
- Modify: `docs/ai-context/architecture.md` (append-only)
- Modify: `CLAUDE.md` (Modules 한 줄 — 세션 종료 직전 권장이나 plan에 포함)

- [ ] **Step 1: Append ADR-010 to architecture.md**

```markdown
## ADR-010: vision 기반 사진 캡션을 초안 생성에 도입
- 상태: Accepted (2026-06-07)
- 맥락: 초안 생성기가 사진을 분석하지 않아 사진과 본문이 불일치(중구난방).
- 결정: 신규 `photo_describer` 모듈이 사진을 EXIF 보정·다운스케일 후 `complete_vision`으로 캡션(content-hash 캐시)하고, `PostGenerator.generate(use_vision=True)`가 캡션을 작성 프롬프트에 주입. `--no-vision`으로 기존 경로-only 폴백.
- 결과: 본문이 사진 내용에 근거하고 흐름에 맞게 배치됨. 비용은 캐시·다운스케일로 완화.
```

- [ ] **Step 2: Add module line to CLAUDE.md**

```markdown
- `photo_describer` — 사진을 vision으로 캡션(EXIF 보정·다운스케일·content-hash 캐시)
```

- [ ] **Step 3: Commit**

```bash
git add docs/ai-context/architecture.md CLAUDE.md
git commit -m "docs: ADR-010 photo-aware generation + CLAUDE.md module"
```

---

## Task 9: Goal 검증 (실사진 28장) + Closeout

**Files:** 없음 (검증 실행 + 자산 점검)

- [ ] **Step 1: 캐시 초기화 후 vision ON 생성 (목표 1·2·5)**

Run (WSL):
```bash
rm -f drafts/.caption-cache.json
uv run naver-bot draft sim/photos/muto-tailor/*.jpg "뮤토 테일러 신랑 예복 맞춤 상담 방문 후기" --profile review
```
Expected: 생성 성공. `uv run naver-bot preview <draft-id>` 후 `.txt`에서 외관 사진 옆 외관 설명, 측정 사진 옆 측정 설명 등 인접 정합 spot-check.

- [ ] **Step 2: 캐시 히트 확인 (목표 4)**

Run: 동일 `draft` 재실행 → `drafts/.caption-cache.json` 존재, 두 번째 실행에서 vision 재호출 없음(로그/시간으로 확인).

- [ ] **Step 3: `--no-vision` 폴백 (목표 3)**

Run: `uv run naver-bot draft sim/photos/muto-tailor/01.jpg "테스트" --profile review --no-vision`
Expected: vision 호출 없이 기존 방식으로 생성.

- [ ] **Step 4: 전체 점검 (목표 6)**

Run: `bash scripts/check.sh`
Expected: lint + 전체 테스트 통과.

- [ ] **Step 5: review-strict drift 검사 + 메모리/문서 sync (RPIC closeout)**

- spec ↔ 구현 일치 확인, gitignore 산출물(`.caption-cache.json`, `.caption-tmp/`) 점검.
- 필요 시 `docs/ai-context/non-obvious.md` 등록 여부 판단.

- [ ] **Step 6: Commit (closeout)**

```bash
git add -A
git commit -m "chore: photo-aware generation cycle closeout"
```

---

## Self-Review (작성자 점검 결과)

- **Spec coverage:** 캡션 모듈(Task1-4)·캐시(Task4)·EXIF/다운스케일(Task3)·generate 통합+프롬프트(Task6)·CLI 기본ON/--no-vision(Task7)·에러폴백(Task4)·테스트(전 Task)·ADR/문서(Task8)·goal 검증(Task9) — spec 모든 항목 매핑됨.
- **Placeholder scan:** 모든 코드 스텝에 실제 코드 포함, TBD/“적절히 처리” 없음.
- **Type consistency:** `PhotoCaption(path,caption,category)`·`describe_photos(paths, vision_client, *, cache_path, work_dir)`·`generate(..., use_vision=True)`·`_build_user_prompt(..., captions=None)`가 전 Task에서 동일 시그니처로 사용됨.
- **주의:** 기존 `test_post_generator.py`의 `FakeClaude`는 `complete_vision`이 없음 → `generate`의 `hasattr(..., "complete_vision")` 가드로 기존 테스트는 vision 미호출(경로-only)로 그대로 통과.
