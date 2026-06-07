**Status:** completed
**RPI-Cycle:** 15
**Started:** 2026-06-08

# MPO Downscale Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix preview image resizing so MPO and other multi-frame still images are downscaled while genuine animated GIF/WebP memes preserve their original frames.

**Authorization note:** The goal document says commit/push only when explicitly requested; the current session goal explicitly requested “머지 푸쉬”, so commit and non-force push are in scope for finalization.

**Architecture:** Keep the existing `preview_command` → `Draft.to_html()` → `_image_data_uri()` → `_resize_image_bytes()` flow. Change only the animation guard inside `_resize_image_bytes()`: preserve original bytes for animated GIF/WebP, otherwise seek multi-frame stills to frame 0 and continue the existing EXIF/downscale/re-encode path.

**Tech Stack:** Python 3.11, uv, Pillow 12.x, pytest, ruff, Typer CLI preview path.

---

## File Structure

- Modify: `tests/unit/test_draft_html.py`
  - Replace the existing false-safety `_animated_gif_bytes()` helper and `test_resize_preserves_animated_gif_meme()` test.
  - Add MPO and genuine animated WEBP fixtures/tests under a new `# --- Cycle 14: MPO multi-frame still ---` section after the Cycle 12 resize block helpers.
- Modify: `src/naver_blog_bot/post_generator/models.py:32-70`
  - Update `_resize_image_bytes()` docstring.
  - Replace the broad `n_frames > 1` passthrough guard with GIF/WebP animated-only passthrough plus `seek(0)` for other multi-frame still images.
- Already updated in Research/Gate R: `CONTEXT.md`, `docs/ai-context/domain-glossary.md`, `docs/ai-context/architecture.md`, `docs/superpowers/specs/2026-06-08-preview-image-resize-design.md`.
- Update during closeout: this plan's checkbox/status lines only.

## Task 1: Add truthful TDD coverage for MPO and genuine animations

**Files:**
- Modify: `tests/unit/test_draft_html.py:126-206`

- [x] **Step 1: Replace the old false-safety GIF helper**

In `tests/unit/test_draft_html.py`, replace the existing `_animated_gif_bytes()` helper with these three helpers:

```python
def _mpo_bytes(width: int = 4032, height: int = 3024) -> bytes:
    # iPhone식 MPO = JPEG 기반 멀티프레임 "정지영상". 재오픈 시
    # format=MPO, n_frames=2, is_animated=True (진짜 움짤과 is_animated 동일 → format만 구분자).
    base = Image.linear_gradient("L").convert("RGB").resize((width, height))
    buf = io.BytesIO()
    base.save(buf, "MPO", save_all=True, append_images=[base], quality=90)
    return buf.getvalue()


def _genuine_animated_gif_bytes(size: int = 600) -> bytes:
    # 4개 "서로 다른" 프레임 → GIF가 프레임을 붕괴시키지 않음(n_frames=4, is_animated=True).
    # size는 반드시 _MEME_MAX_DIM(480)보다 커야 한다. 작으면 within-cap 분기가
    # 가드와 무관하게 None을 반환해 테스트가 false-safety가 된다(실측 확인됨).
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    frames = [Image.new("RGB", (size, size), color=c) for c in colors]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], loop=0, duration=80)
    return buf.getvalue()


def _genuine_animated_webp_bytes(size: int = 600) -> bytes:
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    frames = [Image.new("RGB", (size, size), color=c) for c in colors]
    buf = io.BytesIO()
    frames[0].save(buf, "WEBP", save_all=True, append_images=frames[1:], duration=80, loop=0)
    return buf.getvalue()
```

- [x] **Step 2: Replace the old GIF test and add MPO/WEBP tests**

Delete the old `test_resize_preserves_animated_gif_meme()` body and replace it with the following new section after the existing resize tests:

```python
# --- Cycle 14: MPO multi-frame still ---


def test_resize_shrinks_mpo_still_photo(tmp_path: Path) -> None:
    raw = _mpo_bytes()
    # sanity: 픽스처가 정말 멀티프레임 MPO인지(정직한 실패 보장)
    with Image.open(io.BytesIO(raw)) as probe:
        assert (probe.format or "").upper() == "MPO"
        assert getattr(probe, "n_frames", 1) > 1
    img = tmp_path / "iphone.jpg"  # 아이폰은 MPO를 .jpg 확장자로 저장
    img.write_bytes(raw)
    html = _make_draft(f"[사진: {img}]").to_html()
    embedded = _embedded_bytes(html, "photo")
    assert len(embedded) < len(raw)
    with Image.open(io.BytesIO(embedded)) as out:
        assert max(out.size) <= 1280


def test_resize_preserves_genuine_animated_gif_meme(tmp_path: Path) -> None:
    raw = _genuine_animated_gif_bytes(600)  # > _MEME_MAX_DIM(480) 라야 가드가 실제로 작동
    with Image.open(io.BytesIO(raw)) as probe:
        assert getattr(probe, "n_frames", 1) > 1 and probe.is_animated
    meme = tmp_path / "anim.gif"
    meme.write_bytes(raw)
    html = _make_draft("[짤방: g1]").to_html({"g1": meme})
    assert "data:image/gif;base64," in html
    assert _embedded_bytes(html, "meme") == raw  # 프레임 보존(passthrough, byte-identical)


def test_resize_preserves_genuine_animated_webp_meme(tmp_path: Path) -> None:
    raw = _genuine_animated_webp_bytes(600)
    with Image.open(io.BytesIO(raw)) as probe:
        assert getattr(probe, "n_frames", 1) > 1 and probe.is_animated
    meme = tmp_path / "anim.webp"
    meme.write_bytes(raw)
    html = _make_draft("[짤방: w1]").to_html({"w1": meme})
    assert "data:image/webp;base64," in html
    assert _embedded_bytes(html, "meme") == raw  # 프레임 보존
```

- [x] **Step 3: Run the red MPO test before implementation**

Run:

```bash
uv run pytest -q tests/unit/test_draft_html.py::test_resize_shrinks_mpo_still_photo
```

Expected: FAIL. The failure must show the currently embedded MPO is not downscaled, typically by either `assert len(embedded) < len(raw)` failing or `assert max(out.size) <= 1280` failing.

- [x] **Step 4: Run the genuine animation tests as baseline**

Run:

```bash
uv run pytest -q tests/unit/test_draft_html.py::test_resize_preserves_genuine_animated_gif_meme tests/unit/test_draft_html.py::test_resize_preserves_genuine_animated_webp_meme
```

Expected: PASS on current implementation, because the old broad `n_frames > 1` guard preserves both GIF and WEBP animations. These tests become regression guards after the predicate changes.

## Task 2: Implement the surgical resize predicate fix

**Files:**
- Modify: `src/naver_blog_bot/post_generator/models.py:32-70`
- Test: `tests/unit/test_draft_html.py`

- [x] **Step 1: Update the `_resize_image_bytes()` docstring**

Change the docstring sentence from:

```python
    original bytes). None on: Pillow missing, decode failure, animated image,
```

to:

```python
    original bytes). None on: Pillow missing, decode failure, genuine animated GIF/WebP,
```

- [x] **Step 2: Replace the broad multi-frame passthrough guard**

In `src/naver_blog_bot/post_generator/models.py`, keep `fmt = (im.format or "").upper()` and replace:

```python
            if getattr(im, "n_frames", 1) > 1:
                return None  # animated GIF/WebP: preserve original frames
```

with:

```python
            if fmt in {"GIF", "WEBP"} and getattr(im, "is_animated", False):
                return None  # genuine animated GIF/WebP: preserve frames
            if getattr(im, "n_frames", 1) > 1:
                im.seek(0)  # multi-frame still (iPhone MPO, multi-page TIFF): primary frame
```

Do not change the orientation read, within-cap branch, `ImageOps.exif_transpose()`, `thumbnail()`, format-specific saves, MIME assignments, broad exception fallback, or never-bigger check.

- [x] **Step 3: Run the new focused test set**

Run:

```bash
uv run pytest -q tests/unit/test_draft_html.py::test_resize_shrinks_mpo_still_photo tests/unit/test_draft_html.py::test_resize_preserves_genuine_animated_gif_meme tests/unit/test_draft_html.py::test_resize_preserves_genuine_animated_webp_meme
```

Expected: PASS. This satisfies success criteria [a] and [b].

- [x] **Step 4: Run the full draft HTML unit tests**

Run:

```bash
uv run pytest -q tests/unit/test_draft_html.py
```

Expected: PASS, including existing guards for large photo shrink, small image no-upscale, EXIF orientation, Pillow fallback, PNG/JPEG/WEBP behavior, and placeholder compatibility.

## Task 3: Format, full gate, and real muto HTML measurement

**Files:**
- Modify if formatter changes it: `tests/unit/test_draft_html.py`
- Read/execute only: `sim/measure_muto_html.py`

- [x] **Step 1: Format the changed test file**

Run:

```bash
uv run ruff format tests/unit/test_draft_html.py
```

Expected: file formatted successfully.

- [x] **Step 2: Run the real-path muto measurement**

Run:

```bash
uv run python sim/measure_muto_html.py
```

Expected: PASS-like output showing the `Draft.to_html()` path generated HTML below roughly 15 MB. The goal document records the pre-fix baseline as 152.0 MB; do not use `sim/render_muto_windows.py` or any manual frame-0 bypass.

- [x] **Step 3: Run the full repository gate**

Run:

```bash
./scripts/check.sh
```

Expected: exit 0. This satisfies success criterion [c].

## Task 4: RPI closeout assets and finalization

**Files:**
- Modify: `docs/superpowers/plans/2026-06-08-mpo-downscale.md`
- Modify if needed: `.claude/state.json`
- Do not modify: root `CLAUDE.md` files unless explicitly required at session end.

- [x] **Step 1: Verify success criteria [a]-[e] are met**

Confirm:

```text
[a] test_resize_shrinks_mpo_still_photo passes.
[b] test_resize_preserves_genuine_animated_gif_meme and test_resize_preserves_genuine_animated_webp_meme pass byte-identical assertions.
[c] ./scripts/check.sh exits 0.
[d] uv run python sim/measure_muto_html.py reports muto HTML below roughly 15 MB through Draft.to_html.
[e] Closeout review-strict reports no unresolved drift, glossary/domain distinction handled, and non-obvious registration was considered under the global procedure.
```

Closeout evidence:
- [a] Verified during implementation: focused MPO test passed after the predicate fix.
- [b] Verified during implementation: genuine GIF and WEBP animation tests passed with byte-identical embedded bytes.
- [c] Verified during closeout: `./scripts/check.sh` passed with ruff check, ruff format --check, and 228 pytest tests.
- [d] Verified during closeout: `uv run python sim/measure_muto_html.py` reported `28 photos -> 8.5 MB`, below the ~15 MB target and down from the documented 152.0 MB baseline.
- [e] Domain distinction was added to `CONTEXT.md` and `docs/ai-context/domain-glossary.md`; ADR-012 resolves ADR-008 predicate drift. Non-obvious registration was considered for “멀티프레임==애니메이션 오가정” and “within-cap false-safety 테스트” but not written to `non-obvious.md` in this cycle because global CLAUDE.md §4 requires user confirmation before registering AI-failure learnings.

- [x] **Step 2: Mark every completed task checkbox in this plan**

Change every task checkbox that has been executed from `- [ ]` to `- [x]`. Do not mark a checkbox complete unless the corresponding command/change actually succeeded.

- [x] **Step 3: Commit the implementation and docs**

Run:

```bash
git status --short
git add CONTEXT.md docs/ai-context/architecture.md docs/ai-context/domain-glossary.md docs/superpowers/specs/2026-06-08-preview-image-resize-design.md docs/superpowers/plans/2026-06-08-mpo-downscale.md src/naver_blog_bot/post_generator/models.py tests/unit/test_draft_html.py
git commit -m "fix: downscale MPO preview images" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

Expected: commit succeeds with normal hooks enabled. If pre-commit reports unrelated pre-existing working-tree changes in `.claude/hooks/pre-commit-deny.sh`, `scripts/check.sh`, or `scripts/git-commit.sh`, do not include them in this commit unless explicitly reviewed and required.

- [x] **Step 4: Push main**

Run:

```bash
git push origin main
```

Expected: non-force push succeeds. If WSL credential helper blocks, use the existing project memory guidance for Windows GCM rather than force-pushing.

## Self-Review

- Spec coverage: The plan covers the MPO downscale test, genuine GIF/WEBP preservation tests, surgical `_resize_image_bytes()` predicate/docstring change, full repository gate, real muto measurement, RPI closeout, commit, and push.
- Placeholder scan: No TBD/TODO/fill-in-later placeholders are present. All code and commands are explicit.
- Type/signature consistency: The plan uses existing `Draft.to_html()`, `_embedded_bytes(html, css_class)`, `_resize_image_bytes(raw, max_dim)`, `Image.open`, `Image.linear_gradient`, and `Path` patterns already present in `tests/unit/test_draft_html.py` and `models.py`.
