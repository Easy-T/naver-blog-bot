**Status:** active
**RPI-Cycle:** 6
**Started:** 2026-05-29

# Draft Quality Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** HTML 미리보기 + 클립보드 복사, few-shot 예시 포스트, Claude Vision 기반 짤방 관리(meme-add/fetch/build), 문맥 기반 짤방 배치를 구현한다.

**Architecture:** 6개 서브시스템을 독립 태스크로 구현. 선행 버그 수정(to_cache_text, TextCompleter 중복) → HTML 미리보기 → few-shot → Vision 클라이언트 → meme 명령 → 문맥 기반 배치 순서로 진행.

**Tech Stack:** Python 3.11+, Typer, pydantic, Anthropic SDK, Claude Code CLI subprocess, pyperclip, httpx, pytest, ruff.

---

## File Structure

**신규 파일:**
- `src/naver_blog_bot/shared/protocols.py` — `TextCompleter` 프로토콜 단일 정의
- `src/naver_blog_bot/style_profiler/examples.py` — `ExamplePost` 모델 + `FewShotRepository`
- `tests/unit/test_examples.py` — FewShotRepository 단위 테스트
- `tests/unit/test_draft_html.py` — `Draft.to_html()` 단위 테스트

**수정 파일:**
- `src/naver_blog_bot/style_profiler/models.py` — `to_cache_text()` 캐시 오염 수정
- `src/naver_blog_bot/meme_library/models.py` — `to_cache_text()` 캐시 오염 수정
- `src/naver_blog_bot/shared/claude_client.py` — `complete_vision()` 추가
- `src/naver_blog_bot/post_generator/models.py` — `Draft.to_html()` 추가
- `src/naver_blog_bot/post_generator/generator.py` — few-shot 주입 + `_place_memes_in_draft()` 추가
- `src/naver_blog_bot/style_profiler/refresh.py` — `shared.protocols` 임포트로 교체
- `src/naver_blog_bot/meme_library/service.py` — `tag_meme_image()` 추가
- `src/naver_blog_bot/cli.py` — `preview` 갱신 + `meme-add/fetch/build` 추가
- `pyproject.toml` — `pyperclip`, `httpx` 추가
- `tests/unit/test_style_and_memes.py` — `to_cache_text` 테스트 갱신
- `tests/unit/test_post_generator.py` — FakeClaude 2-call 대응, few-shot/meme-placement 테스트 추가
- `tests/unit/test_claude_client.py` — `complete_vision()` 테스트 추가

---

## Task 1: Prerequisite — to_cache_text 캐시 오염 수정

**Files:**
- Modify: `src/naver_blog_bot/style_profiler/models.py`
- Modify: `src/naver_blog_bot/meme_library/models.py`
- Test: `tests/unit/test_style_and_memes.py`

- [ ] **Step 1: 실패 테스트 추가**

`tests/unit/test_style_and_memes.py`에 아래 테스트를 추가한다:

```python
def test_style_profile_cache_text_excludes_volatile_fields() -> None:
    p1 = StyleProfile(
        blog_url="https://blog.naver.com/flowerbend",
        profile_name="default",
        structure_patterns=["도입부에 개인 경험"],
    )
    import time; time.sleep(0.01)
    p2 = StyleProfile(
        blog_url="https://blog.naver.com/flowerbend",
        profile_name="default",
        structure_patterns=["도입부에 개인 경험"],
    )
    # updated_at이 달라도 캐시 텍스트는 동일해야 한다
    assert p1.to_cache_text() == p2.to_cache_text()
    # blog_url, profile_name은 캐시 텍스트에 포함하지 않는다
    assert "blog_url" not in p1.to_cache_text()
    assert "profile_name" not in p1.to_cache_text()
    assert "updated_at" not in p1.to_cache_text()


def test_meme_index_cache_text_excludes_updated_at() -> None:
    from datetime import datetime, timezone
    idx1 = MemeIndex(updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    idx2 = MemeIndex(updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert idx1.to_cache_text() == idx2.to_cache_text()
    assert "updated_at" not in idx1.to_cache_text()
```

- [ ] **Step 2: 실패 확인**

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
uv run pytest tests/unit/test_style_and_memes.py::test_style_profile_cache_text_excludes_volatile_fields tests/unit/test_style_and_memes.py::test_meme_index_cache_text_excludes_updated_at -v
```

Expected: FAIL

- [ ] **Step 3: StyleProfile.to_cache_text() 수정**

`src/naver_blog_bot/style_profiler/models.py`의 `to_cache_text()`를 아래로 교체한다:

```python
def to_cache_text(self) -> str:
    data = {
        "structure_patterns": self.structure_patterns,
        "tone_keywords": self.tone_keywords,
        "frequent_expressions": self.frequent_expressions,
        "review_conventions": self.review_conventions,
        "photo_usage_notes": self.photo_usage_notes,
        "emoticon_usage_patterns": self.emoticon_usage_patterns,
    }
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
```

- [ ] **Step 4: MemeIndex.to_cache_text() 수정**

`src/naver_blog_bot/meme_library/models.py`의 `to_cache_text()`를 아래로 교체한다:

```python
def to_cache_text(self) -> str:
    data = {"memes": [m.model_dump(mode="json") for m in self.memes]}
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_style_and_memes.py -v
```

Expected: ALL PASS

- [ ] **Step 6: 커밋**

```bash
git add src/naver_blog_bot/style_profiler/models.py src/naver_blog_bot/meme_library/models.py tests/unit/test_style_and_memes.py
git commit -m "fix: exclude volatile fields from to_cache_text to prevent cache misses"
```

---

## Task 2: Prerequisite — TextCompleter 프로토콜 통일

**Files:**
- Create: `src/naver_blog_bot/shared/protocols.py`
- Modify: `src/naver_blog_bot/post_generator/generator.py`
- Modify: `src/naver_blog_bot/style_profiler/refresh.py`

- [ ] **Step 1: shared/protocols.py 생성**

```python
from collections.abc import Sequence
from typing import Protocol


class TextCompleter(Protocol):
    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        cacheable_context: Sequence[str] = (),
    ) -> str: ...
```

- [ ] **Step 2: generator.py에서 로컬 프로토콜 제거**

`src/naver_blog_bot/post_generator/generator.py`에서 `TextCompleter` 클래스 정의를 삭제하고 임포트로 교체한다:

```python
from naver_blog_bot.shared.protocols import TextCompleter
```

(파일 상단 `from collections.abc import Callable, Sequence` 줄에서 `Sequence`가 더 이상 필요없으면 제거. `Protocol` 임포트도 제거.)

- [ ] **Step 3: refresh.py에서 로컬 프로토콜 제거**

`src/naver_blog_bot/style_profiler/refresh.py`에서 `TextCompleter` 클래스 정의를 삭제하고 임포트로 교체한다:

```python
from naver_blog_bot.shared.protocols import TextCompleter
```

- [ ] **Step 4: 전체 테스트 통과 확인**

```bash
uv run pytest tests/ -v
```

Expected: ALL PASS (기존 테스트 변경 없음)

- [ ] **Step 5: 커밋**

```bash
git add src/naver_blog_bot/shared/protocols.py src/naver_blog_bot/post_generator/generator.py src/naver_blog_bot/style_profiler/refresh.py
git commit -m "refactor: unify TextCompleter protocol in shared/protocols.py"
```

---

## Task 3: HTML 미리보기 + 클립보드 복사

**Files:**
- Modify: `src/naver_blog_bot/post_generator/models.py`
- Modify: `src/naver_blog_bot/cli.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/test_draft_html.py` (신규)

- [ ] **Step 1: pyperclip 의존성 추가**

`pyproject.toml`의 `dependencies` 목록에 추가:

```toml
dependencies = [
  "anthropic>=0.72.0",
  "httpx>=0.27.0",
  "playwright>=1.40.0",
  "pyperclip>=1.9.0",
  "pydantic>=2.10.0",
  "pydantic-settings>=2.6.0",
  "typer>=0.21.1",
]
```

(`httpx`도 Task 6을 위해 미리 추가. `uv sync`는 Task 6 이후 한 번에 실행.)

- [ ] **Step 2: 실패 테스트 작성**

`tests/unit/test_draft_html.py` 신규 생성:

```python
from datetime import datetime, timezone
from pathlib import Path

from naver_blog_bot.post_generator.models import Draft


def _make_draft(body: str) -> Draft:
    return Draft(
        id="draft-20260529-120000",
        title="테스트 초안",
        memo="테스트 메모",
        body_markdown=body,
        photo_paths=[Path("photos/a.jpg")],
        created_at=datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_to_html_contains_title() -> None:
    draft = _make_draft("# 제목\n\n본문입니다.")
    html = draft.to_html()
    assert "테스트 초안" in html
    assert "<h1>" in html


def test_to_html_renders_photo_placeholder() -> None:
    draft = _make_draft("[사진: photos/a.jpg]")
    html = draft.to_html()
    assert "photo-placeholder" in html
    assert "photos/a.jpg" in html


def test_to_html_renders_emoticon_badge() -> None:
    draft = _make_draft("재미있었어요. {{이모티콘:기쁨}}")
    html = draft.to_html()
    assert "emoticon-badge" in html
    assert "기쁨" in html


def test_to_html_renders_meme_placeholder() -> None:
    draft = _make_draft("[짤방: satisfied]")
    html = draft.to_html()
    assert "meme-placeholder" in html
    assert "satisfied" in html


def test_to_html_escapes_html_special_chars() -> None:
    draft = _make_draft("A < B & C > D")
    html = draft.to_html()
    assert "<p>A &lt; B &amp; C &gt; D</p>" in html


def test_to_html_is_valid_html_structure() -> None:
    draft = _make_draft("본문")
    html = draft.to_html()
    assert html.startswith("<!DOCTYPE html>")
    assert "<html lang=\"ko\">" in html
    assert "</html>" in html
```

- [ ] **Step 3: 실패 확인**

```bash
uv run pytest tests/unit/test_draft_html.py -v
```

Expected: FAIL (to_html not defined)

- [ ] **Step 4: Draft.to_html() 구현**

`src/naver_blog_bot/post_generator/models.py`에 임포트 추가 후 `to_html()` 메서드를 `Draft` 클래스에 추가:

```python
import html as _html
import re
```

클래스 내부 (preview_text 아래):

```python
def to_html(self) -> str:
    lines: list[str] = []
    for line in self.body_markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("<br>")
            continue
        if stripped.startswith("[사진:"):
            path = stripped[4:-1].strip()
            lines.append(
                f'<div class="photo-placeholder">📷 {_html.escape(path)}</div>'
            )
        elif stripped.startswith("[짤방:"):
            ref = stripped[4:-1].strip()
            lines.append(
                f'<div class="meme-placeholder">🖼️ 짤방: {_html.escape(ref)}</div>'
            )
        elif stripped.startswith("### "):
            lines.append(f"<h3>{_html.escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            lines.append(f"<h2>{_html.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            lines.append(f"<h1>{_html.escape(stripped[2:])}</h1>")
        else:
            processed = re.sub(
                r"\{\{이모티콘:([^}]+)\}\}",
                lambda m: f'<span class="emoticon-badge">😊 {_html.escape(m.group(1))}</span>',
                _html.escape(line),
            )
            lines.append(f"<p>{processed}</p>")

    body_html = "\n".join(lines)
    escaped_title = _html.escape(self.title)
    escaped_memo = _html.escape(self.memo)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{escaped_title}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap" rel="stylesheet">
<style>
body{{font-family:'Noto Sans KR',sans-serif;background:#f5f5f5;margin:0;padding:20px}}
.post{{max-width:720px;margin:0 auto;background:#fff;padding:40px;border-radius:8px}}
.meta{{color:#888;font-size:13px;margin-bottom:20px;border-bottom:1px solid #eee;padding-bottom:16px}}
.photo-placeholder{{background:#e0e0e0;border:2px dashed #bbb;padding:30px;text-align:center;margin:16px 0;border-radius:4px;color:#666}}
.meme-placeholder{{background:#fff3e0;border:2px dashed #ffb74d;padding:20px;text-align:center;margin:16px 0;border-radius:4px;color:#e65100}}
.emoticon-badge{{background:#fff9c4;border:1px solid #f9a825;border-radius:12px;padding:2px 8px;font-size:13px}}
h1{{font-size:24px}}h2{{font-size:20px}}h3{{font-size:17px}}
p{{line-height:1.8;margin:8px 0}}
</style>
</head>
<body>
<div class="post">
<div class="meta">
  <strong>{escaped_title}</strong><br>
  Draft ID: {_html.escape(self.id)}<br>
  Created: {self.created_at.isoformat()}<br>
  Memo: {escaped_memo}
</div>
{body_html}
</div>
</body>
</html>"""
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_draft_html.py -v
```

Expected: ALL PASS

- [ ] **Step 6: preview_command() 갱신**

`src/naver_blog_bot/cli.py`에서 임포트 추가:

```python
import webbrowser
```

그리고:

```python
try:
    import pyperclip
    _PYPERCLIP_AVAILABLE = True
except ImportError:
    _PYPERCLIP_AVAILABLE = False
```

`preview_command()`를 아래로 교체:

```python
@app.command("preview")
def preview_command(
    draft_id: Annotated[str, typer.Argument(help="Draft ID to preview.")],
) -> None:
    settings = get_settings()
    try:
        draft = DraftRepository(settings.drafts_dir).load(draft_id)
    except FileNotFoundError:
        typer.echo(f"Draft not found: {draft_id}")
        raise typer.Exit(1)

    html_path = settings.drafts_dir / f"{draft_id}.html"
    html_path.write_text(draft.to_html(), encoding="utf-8")
    webbrowser.open(html_path.as_uri())

    if _PYPERCLIP_AVAILABLE:
        try:
            pyperclip.copy(draft.body_markdown)
            typer.echo(f"Preview opened: {html_path}\nContent copied to clipboard.")
        except Exception:
            typer.echo(f"Preview opened: {html_path}\n(Clipboard copy failed — install xclip or xsel on WSL2.)")
    else:
        typer.echo(f"Preview opened: {html_path}\n(pyperclip not available — run 'uv sync' to enable clipboard.)")
```

- [ ] **Step 7: uv sync 실행**

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot && uv sync
```

- [ ] **Step 8: 전체 테스트 확인**

```bash
uv run pytest tests/ -v
```

Expected: ALL PASS

- [ ] **Step 9: 커밋**

```bash
git add src/naver_blog_bot/post_generator/models.py src/naver_blog_bot/cli.py pyproject.toml tests/unit/test_draft_html.py
git commit -m "feat: add HTML preview with browser open and clipboard copy"
```

---

## Task 4: Few-shot 예시 포스트 저장 (profile-refresh)

**Files:**
- Create: `src/naver_blog_bot/style_profiler/examples.py`
- Modify: `src/naver_blog_bot/cli.py`
- Test: `tests/unit/test_examples.py` (신규)

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/test_examples.py` 신규 생성:

```python
from pathlib import Path

from naver_blog_bot.style_profiler.examples import ExamplePost, FewShotRepository


def test_few_shot_repository_round_trip(tmp_path: Path) -> None:
    repo = FewShotRepository(tmp_path / "examples.json")
    examples = [
        ExamplePost(
            title="카페 후기",
            url="https://blog.naver.com/flowerbend/1",
            structured_text="오늘 방문한 카페는 [이미지] 분위기가 정말 좋았어요.",
        ),
        ExamplePost(
            title="제품 리뷰",
            url="https://blog.naver.com/flowerbend/2",
            structured_text="이 제품 너무 마음에 들어요. [이모티콘:만족]",
        ),
    ]

    repo.save(examples)
    loaded = repo.load()

    assert len(loaded) == 2
    assert loaded[0].title == "카페 후기"
    assert loaded[1].structured_text == "이 제품 너무 마음에 들어요. [이모티콘:만족]"


def test_few_shot_repository_missing_file_returns_empty(tmp_path: Path) -> None:
    repo = FewShotRepository(tmp_path / "missing.json")
    assert repo.load() == []
    assert not repo.exists()


def test_few_shot_repository_exists_after_save(tmp_path: Path) -> None:
    repo = FewShotRepository(tmp_path / "examples.json")
    repo.save([ExamplePost(title="t", url="u", structured_text="s")])
    assert repo.exists()


def test_few_shot_repository_saves_at_most_three(tmp_path: Path) -> None:
    repo = FewShotRepository(tmp_path / "examples.json")
    examples = [
        ExamplePost(title=f"글{i}", url=f"url{i}", structured_text=f"본문{i}")
        for i in range(5)
    ]
    repo.save(examples)
    assert len(repo.load()) == 3
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/unit/test_examples.py -v
```

Expected: FAIL

- [ ] **Step 3: examples.py 구현**

`src/naver_blog_bot/style_profiler/examples.py` 신규 생성:

```python
from pathlib import Path

from pydantic import BaseModel

from naver_blog_bot.storage.json_store import read_json, write_json

_MAX_EXAMPLES = 3


class ExamplePost(BaseModel):
    title: str
    url: str
    structured_text: str


class FewShotRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, examples: list[ExamplePost]) -> None:
        kept = examples[:_MAX_EXAMPLES]
        write_json(self.path, [e.model_dump() for e in kept])

    def load(self) -> list[ExamplePost]:
        if not self.path.exists():
            return []
        return [ExamplePost(**item) for item in read_json(self.path)]

    def exists(self) -> bool:
        return self.path.exists()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_examples.py -v
```

Expected: ALL PASS

- [ ] **Step 5: profile_refresh_command() 에 examples 저장 추가**

`src/naver_blog_bot/cli.py`에 임포트 추가:

```python
from naver_blog_bot.style_profiler.examples import ExamplePost, FewShotRepository
```

`profile_refresh_command()` 안에서 `save_style_profile(...)` 호출 직후에 아래 코드를 추가:

```python
    url_examples: list[ExamplePost] = []
    for source in sources:
        if _is_url_source(source):
            try:
                docs = scrape_source(source, count, settings)
                for doc in docs:
                    url_examples.append(
                        ExamplePost(
                            title=doc.title or "",
                            url=doc.url,
                            structured_text=doc.to_structured_text(),
                        )
                    )
            except Exception:
                pass

    if url_examples:
        examples_path = settings.style_profiles_dir / f"{profile}-examples.json"
        FewShotRepository(examples_path).save(url_examples)
        typer.echo(f"Style profile saved: {save_path} ({len(sample_texts)} sample(s) used)")
    else:
        typer.echo(f"Style profile saved: {save_path} ({len(sample_texts)} sample(s) used)")
```

> **주의:** 위 코드는 기존 `typer.echo(...)` 줄을 대체하지 않고 그 줄을 제거한 뒤 위 블록으로 교체한다.

실제 교체 범위: 기존의 마지막 줄 `typer.echo(f"Style profile saved: ...")` 을 제거하고 위 블록 전체로 바꾼다.

- [ ] **Step 6: 전체 테스트 확인**

```bash
uv run pytest tests/ -v
```

Expected: ALL PASS

- [ ] **Step 7: 커밋**

```bash
git add src/naver_blog_bot/style_profiler/examples.py src/naver_blog_bot/cli.py tests/unit/test_examples.py
git commit -m "feat: save few-shot example posts during profile-refresh"
```

---

## Task 5: Few-shot 예시 포스트 draft 주입

**Files:**
- Modify: `src/naver_blog_bot/post_generator/generator.py`
- Modify: `src/naver_blog_bot/cli.py`
- Test: `tests/unit/test_post_generator.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/test_post_generator.py`의 `FakeClaude`를 아래로 교체 (call 추적 추가):

```python
class FakeClaude:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def complete_text(self, **kwargs: object) -> str:
        self.calls.append(dict(kwargs))
        if len(self.calls) == 1:
            return "# 포포몬 체험단 후기\n\n사진을 보니 첫인상이 정말 좋았어요."
        # 2nd call (meme placement): return body extracted from user_prompt
        user_prompt = str(kwargs.get("user_prompt", ""))
        if "초안:\n\n" in user_prompt and "\n\n짤방 목록:" in user_prompt:
            return user_prompt.split("초안:\n\n")[1].split("\n\n짤방 목록:")[0]
        return user_prompt
```

기존 테스트에서 `fake.last_call`을 `fake.calls[0]`으로 모두 교체한다.

그리고 파일 끝에 few-shot 주입 테스트 추가:

```python
from naver_blog_bot.style_profiler.examples import ExamplePost


def test_post_generator_injects_few_shot_examples() -> None:
    fake = FakeClaude()
    now = datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc)
    settings = Settings()
    generator = PostGenerator(settings=settings, claude_client=fake, now=lambda: now)
    style_profile = StyleProfile(blog_url="https://blog.naver.com/flowerbend")
    meme_index = MemeIndex()
    examples = [
        ExamplePost(
            title="카페 후기",
            url="https://blog.naver.com/flowerbend/1",
            structured_text="오늘 카페 정말 좋았어요.",
        )
    ]

    generator.generate(
        photo_paths=[Path("photos/a.jpg")],
        memo="카페 방문",
        style_profile=style_profile,
        meme_index=meme_index,
        examples=examples,
    )

    assert "카페 후기" in fake.calls[0]["user_prompt"]
    assert "오늘 카페 정말 좋았어요." in fake.calls[0]["user_prompt"]
    assert "참고 예시" in fake.calls[0]["user_prompt"]


def test_post_generator_works_without_examples() -> None:
    fake = FakeClaude()
    now = datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc)
    settings = Settings()
    generator = PostGenerator(settings=settings, claude_client=fake, now=lambda: now)
    style_profile = StyleProfile(blog_url="https://blog.naver.com/flowerbend")
    meme_index = MemeIndex()

    draft = generator.generate(
        photo_paths=[Path("photos/a.jpg")],
        memo="테스트",
        style_profile=style_profile,
        meme_index=meme_index,
        examples=None,
    )

    assert draft.body_markdown  # 에러 없이 생성됨
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/unit/test_post_generator.py -v
```

Expected: FAIL (generate() has no `examples` param)

- [ ] **Step 3: PostGenerator.generate() 에 examples 파라미터 추가**

`src/naver_blog_bot/post_generator/generator.py`에 임포트 추가:

```python
from naver_blog_bot.style_profiler.examples import ExamplePost
```

`generate()` 시그니처 변경:

```python
def generate(
    self,
    *,
    photo_paths: list[Path],
    memo: str,
    style_profile: StyleProfile,
    meme_index: MemeIndex,
    examples: list[ExamplePost] | None = None,
) -> Draft:
```

`_build_user_prompt()` 호출 부분에서 `examples` 전달:

```python
body_markdown = self.claude_client.complete_text(
    system_prompt=SYSTEM_PROMPT,
    cacheable_context=[
        style_profile.to_cache_text(),
        meme_index.to_cache_text(),
    ],
    user_prompt=self._build_user_prompt(photo_paths, memo, selected_memes, examples),
)
```

`_build_user_prompt()` 시그니처 및 구현 변경:

```python
def _build_user_prompt(
    self,
    photo_paths: list[Path],
    memo: str,
    selected_memes: list[MemeAsset],
    examples: list[ExamplePost] | None,
) -> str:
    photos = "\n".join(f"- {path}" for path in photo_paths)
    memes = (
        "\n".join(
            f"- {meme.id}: {meme.path} ({', '.join(meme.use_cases)})"
            for meme in selected_memes
        )
        or "- 선택된 짤방 없음"
    )

    examples_section = ""
    if examples:
        parts = []
        for i, ex in enumerate(examples, start=1):
            parts.append(f"[예시 {i}] {ex.title}\n{ex.structured_text}")
        examples_section = "\n\n참고 예시 포스트 (문체 참고용):\n" + "\n\n".join(parts)

    return f"""다음 메모와 사진 목록을 바탕으로 네이버 블로그 초안을 작성해줘.{examples_section}

메모:
{memo}

사진 경로:
{photos}

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

- [ ] **Step 4: cli.py의 draft_command()에 examples 로드 추가**

`src/naver_blog_bot/cli.py`에서 `draft_command()` 내부, `style_profile = load_style_profile(...)` 줄 다음에 추가:

```python
    from naver_blog_bot.style_profiler.examples import FewShotRepository
    examples_path = settings.style_profiles_dir / f"{profile}-examples.json"
    examples = FewShotRepository(examples_path).load() or None
```

그리고 `build_generator(settings).generate(...)` 호출에 `examples=examples` 추가:

```python
    draft = build_generator(settings).generate(
        photo_paths=photo_paths,
        memo=memo,
        style_profile=style_profile,
        meme_index=meme_index,
        examples=examples,
    )
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_post_generator.py -v
```

Expected: ALL PASS

- [ ] **Step 6: 전체 테스트 확인**

```bash
uv run pytest tests/ -v
```

Expected: ALL PASS

- [ ] **Step 7: 커밋**

```bash
git add src/naver_blog_bot/post_generator/generator.py src/naver_blog_bot/cli.py tests/unit/test_post_generator.py
git commit -m "feat: inject few-shot example posts into draft generation prompt"
```

---

## Task 6: Vision 클라이언트 확장

**Files:**
- Modify: `src/naver_blog_bot/shared/claude_client.py`
- Test: `tests/unit/test_claude_client.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/test_claude_client.py`에 추가:

```python
def test_claude_code_vision_client_builds_correct_args(monkeypatch) -> None:
    calls = []

    def fake_run(args, *, input, capture_output, text, check, timeout):
        calls.append(args)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps({"type": "result", "result": '{"tags": ["만족"], "use_cases": ["후기 마무리"], "alt_text": "만족 표정"}'}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = ClaudeCodeTextClient(settings=Settings())
    result = client.complete_vision(
        image_path=Path("/tmp/test.jpg"),
        prompt="이 이미지를 분석해라",
    )

    assert result == '{"tags": ["만족"], "use_cases": ["후기 마무리"], "alt_text": "만족 표정"}'
    assert "--image" in calls[0]
    assert "/tmp/test.jpg" in calls[0]


def test_claude_code_vision_raises_on_failure(monkeypatch) -> None:
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="image not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = ClaudeCodeTextClient(settings=Settings())

    with pytest.raises(ClaudeBackendError) as exc:
        client.complete_vision(image_path=Path("/tmp/x.jpg"), prompt="분석해라")

    assert "Claude Code CLI failed" in str(exc.value)
```

파일 상단 임포트에 `Path` 추가:
```python
from pathlib import Path
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/unit/test_claude_client.py::test_claude_code_vision_client_builds_correct_args tests/unit/test_claude_client.py::test_claude_code_vision_raises_on_failure -v
```

Expected: FAIL

- [ ] **Step 3: ClaudeCodeTextClient.complete_vision() 구현**

`src/naver_blog_bot/shared/claude_client.py`의 `ClaudeCodeTextClient` 클래스에 추가:

```python
def complete_vision(self, *, image_path: Path, prompt: str) -> str:
    args = [
        self.settings.claude_command,
        "-p",
        "--output-format",
        "json",
        "--model",
        self.settings.claude_model,
        "--image",
        str(image_path),
    ]
    try:
        result = subprocess.run(
            args,
            input=prompt,
            capture_output=True,
            text=True,
            check=False,
            timeout=self.settings.claude_cli_timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise ClaudeBackendError(
            "Claude Code CLI not found. Install Claude Code or set "
            "NAVER_BOT_CLAUDE_BACKEND=anthropic-sdk with ANTHROPIC_API_KEY."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ClaudeBackendError(
            f"Claude Code CLI timed out after {self.settings.claude_cli_timeout_seconds}s."
        ) from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise ClaudeBackendError(
            f"Claude Code CLI failed. Detail: {detail}"
        )
    return self._parse_output(result.stdout)
```

파일 상단에 `Path` 임포트 추가 (없으면):
```python
from pathlib import Path
```

`ClaudeTextClient`에도 동일 시그니처의 `complete_vision()` 추가 (SDK 경로):

```python
def complete_vision(self, *, image_path: Path, prompt: str) -> str:
    import base64

    image_data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")
    suffix = image_path.suffix.lower().lstrip(".")
    media_type = f"image/{suffix}" if suffix in ("jpg", "jpeg", "png", "gif", "webp") else "image/jpeg"

    message = self.client.messages.create(
        model=self.settings.claude_model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    parts = []
    for block in message.content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block["text"]))
        elif getattr(block, "type", None) == "text":
            parts.append(str(block.text))
    return "".join(parts).strip()
```

- [ ] **Step 4: VisionCompleter 프로토콜 추가**

`src/naver_blog_bot/shared/protocols.py`에 추가:

```python
class VisionCompleter(Protocol):
    def complete_vision(self, *, image_path: Path, prompt: str) -> str: ...
```

파일 상단에 `Path` 임포트 추가:
```python
from pathlib import Path
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_claude_client.py -v
```

Expected: ALL PASS

- [ ] **Step 6: 커밋**

```bash
git add src/naver_blog_bot/shared/claude_client.py src/naver_blog_bot/shared/protocols.py tests/unit/test_claude_client.py
git commit -m "feat: add complete_vision() to Claude clients for image analysis"
```

---

## Task 7: meme-add 명령

**Files:**
- Modify: `src/naver_blog_bot/meme_library/service.py`
- Modify: `src/naver_blog_bot/cli.py`
- Test: `tests/unit/test_style_and_memes.py`

- [ ] **Step 1: 실패 테스트 추가**

`tests/unit/test_style_and_memes.py`에 추가:

```python
def test_tag_meme_image_parses_vision_response(tmp_path: Path) -> None:
    from naver_blog_bot.meme_library.service import tag_meme_image

    image_path = tmp_path / "happy.jpg"
    image_path.write_bytes(b"fake image")

    class FakeVisionClient:
        def complete_vision(self, *, image_path, prompt):
            return '{"tags": ["기쁨", "만족"], "use_cases": ["후기 마무리", "만족 표현"], "alt_text": "기쁜 표정"}'

    asset = tag_meme_image(image_path, FakeVisionClient())
    assert asset.id == "happy"
    assert asset.path == image_path
    assert "기쁨" in asset.tags
    assert "후기 마무리" in asset.use_cases
    assert asset.alt_text == "기쁜 표정"


def test_tag_meme_image_handles_invalid_json(tmp_path: Path) -> None:
    import pytest
    from naver_blog_bot.meme_library.service import tag_meme_image

    image_path = tmp_path / "bad.jpg"
    image_path.write_bytes(b"fake")

    class BrokenVision:
        def complete_vision(self, *, image_path, prompt):
            return "이건 JSON이 아님"

    with pytest.raises(ValueError, match="Vision"):
        tag_meme_image(image_path, BrokenVision())
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/unit/test_style_and_memes.py::test_tag_meme_image_parses_vision_response tests/unit/test_style_and_memes.py::test_tag_meme_image_handles_invalid_json -v
```

Expected: FAIL

- [ ] **Step 3: tag_meme_image() 구현**

`src/naver_blog_bot/meme_library/service.py`를 아래로 교체:

```python
import json
from pathlib import Path
from typing import Any

from naver_blog_bot.meme_library.models import MemeAsset, MemeIndex
from naver_blog_bot.storage.json_store import read_json, write_json

_VISION_PROMPT = """이 이미지에 어울리는 한국어 블로그 짤방 메타데이터를 JSON으로 반환해라.
JSON 외 다른 텍스트는 반환하지 마라.
{
  "tags": ["감정/분위기를 나타내는 한국어 키워드 3-6개"],
  "use_cases": ["이 짤방을 쓰기 좋은 상황 2-4개"],
  "alt_text": "이미지를 한 줄로 설명"
}"""


def load_meme_index(path: Path) -> MemeIndex:
    if not path.exists():
        return MemeIndex()
    return MemeIndex.model_validate(read_json(path))


def save_meme_index(path: Path, index: MemeIndex) -> None:
    write_json(path, index.model_dump(mode="json"))


def tag_meme_image(image_path: Path, vision_client: Any) -> MemeAsset:
    raw = vision_client.complete_vision(image_path=image_path, prompt=_VISION_PROMPT)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Vision client returned invalid JSON: {raw[:100]}") from exc
    return MemeAsset(
        id=image_path.stem,
        path=image_path,
        tags=data.get("tags", []),
        use_cases=data.get("use_cases", []),
        alt_text=data.get("alt_text", ""),
    )


def add_or_update_meme(index: MemeIndex, asset: MemeAsset) -> MemeIndex:
    memes = [m for m in index.memes if m.id != asset.id]
    memes.append(asset)
    return MemeIndex(memes=memes)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_style_and_memes.py -v
```

Expected: ALL PASS

- [ ] **Step 5: meme_add_command() CLI 추가**

`src/naver_blog_bot/cli.py`에서 임포트 추가:

```python
from naver_blog_bot.meme_library.service import (
    add_or_update_meme,
    load_meme_index,
    save_meme_index,
    tag_meme_image,
)
```

기존 `meme_build_command()`를 아래로 **교체**:

```python
@app.command("meme-add")
def meme_add_command(
    image_path: Annotated[Path, typer.Argument(help="Path to meme image file.")],
) -> None:
    if not image_path.is_file():
        typer.echo(f"Error: file not found: {image_path}")
        raise typer.Exit(1)
    settings = get_settings()
    try:
        asset = tag_meme_image(image_path, build_text_completer(settings))
    except (ClaudeBackendError, ValueError) as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)
    index = load_meme_index(settings.meme_index_path)
    updated = add_or_update_meme(index, asset)
    save_meme_index(settings.meme_index_path, updated)
    typer.echo(f"Added: {image_path.name} (tags: {', '.join(asset.tags)})")


@app.command("meme-build")
def meme_build_command() -> None:
    settings = get_settings()
    ensure_local_directories(settings)
    index = load_meme_index(settings.meme_index_path)
    existing_ids = {m.id for m in index.memes}
    extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    new_count = 0
    for image_path in sorted(settings.memes_dir.iterdir()):
        if image_path.suffix.lower() not in extensions:
            continue
        if image_path.stem in existing_ids:
            continue
        try:
            asset = tag_meme_image(image_path, build_text_completer(settings))
            index = add_or_update_meme(index, asset)
            new_count += 1
            typer.echo(f"Tagged: {image_path.name}")
        except (ClaudeBackendError, ValueError) as exc:
            typer.echo(f"Skipped {image_path.name}: {exc}")
    save_meme_index(settings.meme_index_path, index)
    skipped = len(existing_ids)
    typer.echo(f"Done: {new_count} new image(s) tagged, {skipped} existing skipped.")
```

> **주의:** `build_text_completer`가 `VisionCompleter` 프로토콜을 만족하는지 확인. `ClaudeCodeTextClient`와 `ClaudeTextClient` 모두 `complete_vision()`을 가지므로 타입 호환 됨.

- [ ] **Step 6: 전체 테스트 확인**

```bash
uv run pytest tests/ -v
```

Expected: ALL PASS

- [ ] **Step 7: 커밋**

```bash
git add src/naver_blog_bot/meme_library/service.py src/naver_blog_bot/cli.py tests/unit/test_style_and_memes.py
git commit -m "feat: add meme-add and meme-build commands with Claude Vision auto-tagging"
```

---

## Task 8: meme-fetch 명령

**Files:**
- Modify: `src/naver_blog_bot/cli.py`
- Test: `tests/unit/test_cli.py`

- [ ] **Step 1: 실패 테스트 추가**

`tests/unit/test_cli.py`에 추가 (파일 상단 확인 후 필요한 임포트 추가):

```python
def test_meme_fetch_downloads_image_and_tags(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    from naver_blog_bot.config import Settings, ensure_local_directories
    settings = Settings()
    ensure_local_directories(settings)

    fake_image_bytes = b"\xff\xd8\xff" + b"fake jpeg content"

    class FakeResponse:
        status_code = 200
        content = fake_image_bytes
        headers = {"content-type": "image/jpeg"}

    import httpx
    monkeypatch.setattr(httpx, "get", lambda url, **kwargs: FakeResponse())

    class FakeTagger:
        def complete_vision(self, *, image_path, prompt):
            return '{"tags": ["재미"], "use_cases": ["유머"], "alt_text": "재미있는 짤방"}'

    monkeypatch.setattr(cli, "build_text_completer", lambda s: FakeTagger())

    result = runner.invoke(cli.app, ["meme-fetch", "https://example.com/funny.jpg"])

    assert result.exit_code == 0
    assert "Fetched" in result.stdout or "Added" in result.stdout
    meme_files = list(settings.memes_dir.iterdir())
    assert len(meme_files) == 1
    assert meme_files[0].suffix == ".jpg"
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/unit/test_cli.py::test_meme_fetch_downloads_image_and_tags -v
```

Expected: FAIL

- [ ] **Step 3: meme-fetch 명령 구현**

`src/naver_blog_bot/cli.py`에서 `meme_add_command()` 다음에 추가:

```python
@app.command("meme-fetch")
def meme_fetch_command(
    url: Annotated[str, typer.Argument(help="Image URL to download and register.")],
) -> None:
    import httpx
    from urllib.parse import urlparse

    settings = get_settings()
    ensure_local_directories(settings)

    try:
        response = httpx.get(url, follow_redirects=True, timeout=30)
        response.raise_for_status()
    except Exception as exc:
        typer.echo(f"Error downloading image: {exc}")
        raise typer.Exit(1)

    content_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    ext = ext_map.get(content_type, ".jpg")

    parsed_name = Path(urlparse(url).path).stem or "meme"
    dest = settings.memes_dir / f"{parsed_name}{ext}"
    counter = 2
    while dest.exists():
        dest = settings.memes_dir / f"{parsed_name}-{counter}{ext}"
        counter += 1

    dest.write_bytes(response.content)

    try:
        asset = tag_meme_image(dest, build_text_completer(settings))
    except (ClaudeBackendError, ValueError) as exc:
        dest.unlink(missing_ok=True)
        typer.echo(f"Error tagging image: {exc}")
        raise typer.Exit(1)

    index = load_meme_index(settings.meme_index_path)
    updated = add_or_update_meme(index, asset)
    save_meme_index(settings.meme_index_path, updated)
    typer.echo(f"Fetched and added: {dest.name} (tags: {', '.join(asset.tags)})")
```

- [ ] **Step 4: uv sync**

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot && uv sync
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_cli.py::test_meme_fetch_downloads_image_and_tags -v
```

Expected: PASS

- [ ] **Step 6: 전체 테스트 확인**

```bash
uv run pytest tests/ -v
```

Expected: ALL PASS

- [ ] **Step 7: 커밋**

```bash
git add src/naver_blog_bot/cli.py tests/unit/test_cli.py
git commit -m "feat: add meme-fetch command to download and register meme images by URL"
```

---

## Task 9: 문맥 기반 짤방 배치

**Files:**
- Modify: `src/naver_blog_bot/post_generator/generator.py`
- Test: `tests/unit/test_post_generator.py`

- [ ] **Step 1: 실패 테스트 추가**

`tests/unit/test_post_generator.py`에 추가:

```python
def test_place_memes_in_draft_inserts_markers() -> None:
    class MarkerClaude:
        def complete_text(self, **kwargs):
            # 짤방 배치 결과 시뮬레이션
            return "# 제목\n\n좋았어요.\n[짤방: satisfied]\n\n마무리."

    settings = Settings()
    generator = PostGenerator(settings=settings, claude_client=MarkerClaude())
    meme_index = MemeIndex(
        memes=[
            MemeAsset(
                id="satisfied",
                path=Path("assets/memes/satisfied.png"),
                tags=["만족"],
                use_cases=["만족 표현"],
                alt_text="만족",
            )
        ]
    )
    body = "# 제목\n\n좋았어요.\n\n마무리."

    result = generator._place_memes_in_draft(body, meme_index)

    assert "[짤방: satisfied]" in result


def test_place_memes_skips_when_no_memes() -> None:
    class NeverCalled:
        def complete_text(self, **kwargs):
            raise AssertionError("should not be called")

    settings = Settings()
    generator = PostGenerator(settings=settings, claude_client=NeverCalled())
    body = "본문입니다."

    result = generator._place_memes_in_draft(body, MemeIndex())

    assert result == "본문입니다."
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/unit/test_post_generator.py::test_place_memes_in_draft_inserts_markers tests/unit/test_post_generator.py::test_place_memes_skips_when_no_memes -v
```

Expected: FAIL

- [ ] **Step 3: _place_memes_in_draft() 구현**

`src/naver_blog_bot/post_generator/generator.py`에 상수 추가 (SYSTEM_PROMPT 아래):

```python
MEME_PLACEMENT_SYSTEM = """너는 한국어 블로그 편집자다.
초안과 짤방 목록을 보고, 각 짤방이 자연스럽게 어울리는 문단 바로 다음 줄에 [짤방: {id}] 마커를 삽입해라.
규칙:
- 억지로 넣지 마라. 정말 어울리는 곳에만.
- 짤방 하나는 한 번만 사용.
- 마커 외 본문 텍스트는 절대 수정하지 마라.
- 수정된 초안 전체만 반환해라."""
```

`PostGenerator` 클래스에 메서드 추가:

```python
def _place_memes_in_draft(self, body: str, meme_index: MemeIndex) -> str:
    if not meme_index.memes:
        return body
    meme_list = "\n".join(
        f"- id: {m.id}, use_cases: {', '.join(m.use_cases)}, tags: {', '.join(m.tags)}"
        for m in meme_index.memes
    )
    user_prompt = f"초안:\n\n{body}\n\n짤방 목록:\n{meme_list}"
    return self.claude_client.complete_text(
        system_prompt=MEME_PLACEMENT_SYSTEM,
        user_prompt=user_prompt,
        cacheable_context=[],
    )
```

`generate()` 메서드 안에서 `body_markdown` 생성 직후, `created_at = self.now()` 전에 추가:

```python
body_markdown = self._place_memes_in_draft(body_markdown, meme_index)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/unit/test_post_generator.py -v
```

Expected: ALL PASS

- [ ] **Step 5: 전체 테스트 확인**

```bash
uv run pytest tests/ -v
```

Expected: ALL PASS

- [ ] **Step 6: 커밋**

```bash
git add src/naver_blog_bot/post_generator/generator.py tests/unit/test_post_generator.py
git commit -m "feat: add contextual meme placement via second Claude pass after draft generation"
```

---

## Task 10: 최종 검증

**Files:**
- Verify: 모든 변경 파일

- [ ] **Step 1: quality gate 실행**

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot && bash scripts/check.sh
```

Expected: exit code 0

- [ ] **Step 2: 전체 테스트 재실행**

```bash
uv run pytest tests/ -v --tb=short
```

Expected: ALL PASS

- [ ] **Step 3: 범위 검증 — 변경된 파일 목록 확인**

```bash
git diff --name-only HEAD~9 HEAD
```

Expected 파일 목록 (이 외의 파일이 있으면 검토):
```
pyproject.toml
src/naver_blog_bot/meme_library/models.py
src/naver_blog_bot/meme_library/service.py
src/naver_blog_bot/post_generator/generator.py
src/naver_blog_bot/post_generator/models.py
src/naver_blog_bot/shared/claude_client.py
src/naver_blog_bot/shared/protocols.py
src/naver_blog_bot/style_profiler/examples.py
src/naver_blog_bot/style_profiler/models.py
src/naver_blog_bot/style_profiler/refresh.py
src/naver_blog_bot/cli.py
tests/unit/test_claude_client.py
tests/unit/test_draft_html.py
tests/unit/test_examples.py
tests/unit/test_post_generator.py
tests/unit/test_style_and_memes.py
```

- [ ] **Step 4: 커밋은 이미 태스크별로 완료됨 — 명시적 요청 없이 추가 커밋하지 않는다**

---

## Self-Review

**Spec 커버리지:**
- ✅ to_cache_text 캐시 오염 수정 (Task 1)
- ✅ TextCompleter 프로토콜 통일 (Task 2)
- ✅ HTML 미리보기 + 클립보드 복사 (Task 3)
- ✅ Few-shot 예시 저장 (Task 4) + 주입 (Task 5)
- ✅ Vision 클라이언트 확장 (Task 6)
- ✅ meme-add (Task 7) + meme-build (Task 7) + meme-fetch (Task 8)
- ✅ 문맥 기반 짤방 배치 (Task 9)

**Placeholder 없음:** 모든 단계에 실제 코드 포함.

**타입 일관성:**
- `TextCompleter` → `shared/protocols.py` 단일 정의, Task 2에서 먼저 생성 후 이후 태스크에서 사용
- `VisionCompleter` → Task 6에서 정의, Task 7에서 사용
- `ExamplePost`, `FewShotRepository` → Task 4에서 정의, Task 5에서 사용
- `add_or_update_meme` → Task 7에서 정의, Task 8에서 재사용
