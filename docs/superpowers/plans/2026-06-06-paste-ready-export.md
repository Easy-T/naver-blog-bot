# Paste-Ready SmartEditor Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** active
**RPI-Cycle:** 13
**Started:** 2026-06-06

**Goal:** `naver-bot preview` copies *paste-ready text* (markers rewritten as
human-readable insertion cues, no absolute paths) to the clipboard and saves it
to `drafts/<id>.txt`, instead of dumping raw `body_markdown`.

**Architecture:** New `Draft.to_paste_text(meme_labels=None)` method on the Draft
model — a sibling of `to_html` with the same line-based marker dispatch, but
emitting plain-text 〔…〕 cues. `cli.preview_command` builds an `id → label` map
from the meme index (keeping `models.py` decoupled from `meme_library`, per
ADR-007/009), writes the `.txt`, and copies the paste-text to the clipboard.

**Tech Stack:** Python 3.11+, Typer, pydantic, pytest (via `uv run`). No new deps.

**Spec:** `docs/superpowers/specs/2026-06-06-paste-ready-export-design.md`
**ADR:** ADR-009 in `docs/ai-context/architecture.md`.

---

## File Structure

- `src/naver_blog_bot/post_generator/models.py` — add module regex
  `_EMOTICON_RE`, helper `_emoticon_to_cue`, and method `Draft.to_paste_text`.
  Do NOT touch `to_html`, `_image_data_uri`, or `_resize_image_bytes`.
- `src/naver_blog_bot/cli.py` — `preview_command` only: build `meme_labels`,
  write `<id>.txt`, copy paste-text (not `body_markdown`) to clipboard.
- `tests/unit/test_draft_paste.py` — new unit tests for `to_paste_text`.
- `tests/unit/test_cli.py` — extend with a preview-wiring test.

---

## Task 1: `Draft.to_paste_text` conversion

**Files:**
- Create: `tests/unit/test_draft_paste.py`
- Modify: `src/naver_blog_bot/post_generator/models.py` (add regex + helper +
  method after the `Draft.to_html` method, ~line 187)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_draft_paste.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

from naver_blog_bot.post_generator.models import Draft


def _make_draft(body: str) -> Draft:
    return Draft(
        id="draft-20260606-120000",
        title="테스트 초안",
        memo="메모",
        body_markdown=body,
        photo_paths=[Path("photos/a.jpg")],
        created_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_paste_text_photo_marker_uses_basename_only() -> None:
    out = _make_draft("[사진: /home/indietogo/photos/IMG_1234.jpg]").to_paste_text()
    assert "[사진:" not in out
    assert "/home/" not in out
    assert "IMG_1234.jpg" in out
    assert "📷" in out


def test_paste_text_meme_marker_uses_label_when_present() -> None:
    out = _make_draft("[짤방: m1]").to_paste_text({"m1": "웃음, 만족"})
    assert "[짤방:" not in out
    assert "웃음, 만족" in out
    assert "🖼" in out  # part of 🖼️


def test_paste_text_meme_marker_falls_back_to_id_without_label() -> None:
    out = _make_draft("[짤방: satisfied]").to_paste_text()
    assert "[짤방:" not in out
    assert "satisfied" in out


def test_paste_text_emoticon_marker_preserves_type_inline() -> None:
    out = _make_draft("정말 좋았어요 {{이모티콘:만족}} 추천합니다").to_paste_text()
    assert "{{이모티콘:" not in out
    assert "만족" in out
    assert "😊" in out
    assert "정말 좋았어요" in out
    assert "추천합니다" in out


def test_paste_text_multiple_emoticons_on_one_line() -> None:
    out = _make_draft("좋아요 {{이모티콘:기쁨}} 그리고 {{이모티콘:감탄}}").to_paste_text()
    assert "{{이모티콘:" not in out
    assert "기쁨" in out
    assert "감탄" in out


def test_paste_text_strips_heading_hashes() -> None:
    out = _make_draft("# 제목입니다\n\n## 소제목").to_paste_text()
    assert "제목입니다" in out
    assert "소제목" in out
    assert "#" not in out


def test_paste_text_preserves_plain_paragraph_and_blank_lines() -> None:
    out = _make_draft("첫 문단\n\n둘째 문단").to_paste_text()
    assert "첫 문단\n\n둘째 문단" in out


def test_paste_text_marker_free_text_has_no_cues() -> None:
    out = _make_draft("그냥 평범한 본문입니다.").to_paste_text()
    assert "〔" not in out
    assert "그냥 평범한 본문입니다." in out


def test_paste_text_full_body_no_raw_markers() -> None:
    body = (
        "# 체험단 후기\n\n"
        "[사진: /home/u/IMG_1.jpg]\n\n"
        "정말 좋았어요 {{이모티콘:만족}}\n\n"
        "[짤방: m1]"
    )
    out = _make_draft(body).to_paste_text({"m1": "웃음"})
    assert "[사진:" not in out
    assert "[짤방:" not in out
    assert "{{이모티콘:" not in out
    assert "/home/" not in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_draft_paste.py -v`
Expected: FAIL — `AttributeError: 'Draft' object has no attribute 'to_paste_text'`.

- [ ] **Step 3: Implement `to_paste_text`**

In `src/naver_blog_bot/post_generator/models.py`, add a module-level regex +
helper near the other module constants (after the `_EXIF_ORIENTATION_TAG` block,
before `_resize_image_bytes`). `re` and `Path` are already imported:

```python
_EMOTICON_RE = re.compile(r"\{\{이모티콘:([^}]+)\}\}")


def _emoticon_to_cue(text: str) -> str:
    """Rewrite inline {{이모티콘:유형}} markers as plain-text insertion cues."""
    return _EMOTICON_RE.sub(lambda m: f"〔😊 이모티콘: {m.group(1)}〕", text)
```

Then add the method to the `Draft` class, immediately after `to_html` (after the
closing `"""</html>"""` return, ~line 187):

```python
    def to_paste_text(self, meme_labels: dict[str, str] | None = None) -> str:
        """Render body markers as human-readable SmartEditor insertion cues.

        Photo/meme markers become 〔…〕 cues (basename / label only, no absolute
        paths); inline emoticon markers become 〔😊 …〕; markdown heading hashes
        are stripped; plain paragraphs and blank lines are preserved.
        `meme_labels` maps a meme id to a human label (built by the caller to
        keep this model decoupled from meme_library — ADR-007/009); an unknown
        id falls back to the raw id.
        """
        meme_labels = meme_labels or {}
        out: list[str] = []
        for line in self.body_markdown.splitlines():
            stripped = line.strip()
            if not stripped:
                out.append("")
            elif stripped.startswith("[사진:"):
                name = Path(stripped[4:-1].strip()).name
                out.append(f"〔📷 사진 삽입: {name}〕")
            elif stripped.startswith("[짤방:"):
                ref = stripped[4:-1].strip()
                out.append(f"〔🖼️ 짤방: {meme_labels.get(ref, ref)}〕")
            elif stripped.startswith("### "):
                out.append(_emoticon_to_cue(stripped[4:]))
            elif stripped.startswith("## "):
                out.append(_emoticon_to_cue(stripped[3:]))
            elif stripped.startswith("# "):
                out.append(_emoticon_to_cue(stripped[2:]))
            else:
                out.append(_emoticon_to_cue(line))
        return "\n".join(out)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_draft_paste.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_draft_paste.py src/naver_blog_bot/post_generator/models.py
git commit -m "feat: add Draft.to_paste_text for SmartEditor paste cues (cycle 13)"
```

---

## Task 2: Wire `preview` to write `.txt` + copy paste-text

**Files:**
- Modify: `src/naver_blog_bot/cli.py` — `preview_command` (~lines 238-269)
- Modify: `tests/unit/test_cli.py` — add one preview-wiring test

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_cli.py` (a `FakeClipboard` + test). `Draft`,
`DraftRepository`, `Path`, `cli`, `runner` are already imported at the top:

```python
class FakeClipboard:
    def __init__(self) -> None:
        self.copied: str | None = None

    def copy(self, text: str) -> None:
        self.copied = text


def test_preview_copies_paste_text_and_writes_txt(
    monkeypatch, tmp_path: Path
) -> None:
    configure_paths(monkeypatch, tmp_path)
    clip = FakeClipboard()
    monkeypatch.setattr(cli, "_pyperclip", clip)
    monkeypatch.setattr(cli, "_PYPERCLIP_AVAILABLE", True)
    monkeypatch.setattr(cli, "_open_in_browser", lambda path: None)

    DraftRepository(tmp_path / "drafts").save(
        Draft(
            id="draft-20260606-120000",
            title="체험단 후기",
            memo="메모",
            body_markdown=(
                "# 체험단 후기\n\n"
                "[사진: /home/indietogo/photos/IMG_1234.jpg]\n\n"
                "정말 좋았어요 {{이모티콘:만족}}"
            ),
            photo_paths=[Path("/home/indietogo/photos/IMG_1234.jpg")],
            ogq_artwork_id="644e042a7d7f8",
        )
    )

    result = runner.invoke(cli.app, ["preview", "draft-20260606-120000"])

    assert result.exit_code == 0, result.stdout
    txt_path = tmp_path / "drafts" / "draft-20260606-120000.txt"
    assert txt_path.exists()
    txt = txt_path.read_text(encoding="utf-8")
    assert "[사진:" not in txt
    assert "/home/" not in txt
    assert "IMG_1234.jpg" in txt
    # Clipboard received the paste-text, not raw markdown.
    assert clip.copied == txt
    assert "{{이모티콘:" not in clip.copied
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_cli.py::test_preview_copies_paste_text_and_writes_txt -v`
Expected: FAIL — no `.txt` written and `clip.copied` equals raw `body_markdown`
(still contains `[사진:`), so an assertion fails.

- [ ] **Step 3: Implement the wiring**

Replace the body of `preview_command` in `src/naver_blog_bot/cli.py` from the
`meme_paths = {...}` line through the final `else` echo block with:

```python
    index = load_meme_index(settings.meme_index_path)
    meme_paths = {meme.id: meme.path for meme in index.memes}
    meme_labels = {
        meme.id: (", ".join(meme.tags) if meme.tags else (meme.alt_text or meme.id))
        for meme in index.memes
    }
    html_path = settings.drafts_dir / f"{draft_id}.html"
    html_path.write_text(draft.to_html(meme_paths), encoding="utf-8")

    paste_text = draft.to_paste_text(meme_labels)
    txt_path = settings.drafts_dir / f"{draft_id}.txt"
    txt_path.write_text(paste_text, encoding="utf-8")

    _open_in_browser(html_path)

    if _PYPERCLIP_AVAILABLE:
        try:
            _pyperclip.copy(paste_text)
            typer.echo(
                f"Preview opened: {html_path}\n"
                f"Paste-ready text copied to clipboard (also saved: {txt_path})."
            )
        except Exception:
            typer.echo(
                f"Preview opened: {html_path}\n"
                f"Paste-ready text saved: {txt_path}\n"
                "(Clipboard copy failed — install xclip or xsel on WSL2.)"
            )
    else:
        typer.echo(
            f"Preview opened: {html_path}\n"
            f"Paste-ready text saved: {txt_path}\n"
            "(pyperclip not available — run 'uv sync' to enable clipboard.)"
        )
```

- [ ] **Step 4: Run the new test + the existing preview test to verify they pass**

Run: `uv run pytest tests/unit/test_cli.py -k preview -v`
Expected: PASS — both `test_preview_outputs_saved_draft` (still asserts
"Preview opened:" + the `.html` name, which the new messages keep) and
`test_preview_copies_paste_text_and_writes_txt`.

- [ ] **Step 5: Commit**

```bash
git add src/naver_blog_bot/cli.py tests/unit/test_cli.py
git commit -m "feat: preview copies paste-text + saves drafts/<id>.txt (cycle 13)"
```

---

## Task 3: Full gate verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full check gate**

Run: `bash scripts/check.sh`
Expected: `==> ruff check` clean, `==> ruff format --check` clean, `==> pytest`
shows all tests passed (existing + 9 new paste + 1 new cli), final line
`== check complete ==`.

- [ ] **Step 2: Explicitly verify RC=0 (NOBV-002 — no false green)**

Run: `bash scripts/check.sh; echo "RC=$?"`
Expected: last line `RC=0` AND a `passed` token in the pytest output. If ruff
format reports a diff, run `uv run ruff format .`, re-stage, and re-run. Do NOT
treat a non-zero RC or a missing `passed` token as success.

---

## Self-Review

**1. Spec coverage:**
- Spec "New method `Draft.to_paste_text(meme_labels=None)`" → Task 1 Step 3. ✓
- Spec marker conversions (photo basename / meme label+fallback / emoticon inline
  / heading strip / paragraph+blank preserve) → Task 1 tests + impl. ✓
- Spec "decoupling: dict[str,str], no meme_library import" → Task 1 method takes
  `dict[str, str]`; cli builds the map (Task 2). ✓
- Spec "`preview` writes `<id>.txt` + copies paste-text; graceful paths" → Task 2
  Step 3 (both echo branches keep the `.txt` path; `.txt` written before
  clipboard). ✓
- Spec verification (no raw markers, no `/home/`, label vs id, emoticon type,
  heading text, idempotent marker-free, cli `.txt` == paste-text, clipboard not
  body_markdown) → Task 1 + Task 2 tests. ✓
- Spec `bash scripts/check.sh` RC=0 → Task 3. ✓

**2. Placeholder scan:** No TBD/TODO; every code step has full code. ✓

**3. Type consistency:** `to_paste_text(self, meme_labels: dict[str, str] | None
= None) -> str` used identically in Task 1 (def) and Task 2 (call with
`meme_labels`). `_EMOTICON_RE` / `_emoticon_to_cue` defined in Task 1 Step 3 and
used only there. cue strings (`〔📷 사진 삽입:`, `〔🖼️ 짤방:`, `〔😊 이모티콘:`)
consistent between impl and assertions. ✓
