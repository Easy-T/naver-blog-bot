# Preview Image Resize Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** completed
**RPI-Cycle:** 12
**Started:** 2026-06-06
**Completed:** 2026-06-06

> **Execution result (all tasks done, inline via executing-plans):**
> - Task 1: `pillow>=11.0.0` added (installed 12.2.0); `import PIL` verified. Commit `a856a28`.
> - Task 2+3: `_resize_image_bytes` + `max_dim` + call-site caps; 5 resize tests + 12 back-compat tests green (17/17 in test_draft_html). Commits `579468c` (code+tests), `ee18e23` (spec/ADR/plan). E402 avoided (top imports); ruff format applied.
> - Task 4 smoke: 12-photo spoglia HTML **104MB → 2.06MB / 2.07MB (~50×)**; `<img class="photo">`×12 + `<img class="meme">`×3, placeholder leftover 0; `bash scripts/check.sh` **RC=0** (ruff + format + 161 pytest).
> - Note: per-task commits folded (Task 2+3 combined) to avoid a transient F401 (the EXIF-tag import is consumed by the Task-3 test). drafts/*.html are gitignored — not committed.

**Goal:** Shrink the ~103MB self-contained preview HTML by resizing/re-encoding images with Pillow before base64 embedding, while keeping draft-grade quality and never crashing when Pillow is absent.

**Architecture:** Add a `_resize_image_bytes(raw, max_dim)` helper in `post_generator/models.py` that decodes with Pillow, bakes EXIF orientation, downscales the longest edge to a cap via `thumbnail` (shrink-only), and re-encodes format-preserving. `_image_data_uri` gains an optional `max_dim`; the two call sites pass photo (1280) / meme (480) caps. If Pillow is missing, decode fails, the image is animated, or the re-encode is not smaller, the helper returns `None` and the caller embeds the original bytes (Cycle-11 behavior).

**Tech Stack:** Python 3.11, Pillow ≥11, pytest, uv, ruff (default E/F rules, line-length 88).

Spec: `docs/superpowers/specs/2026-05-31-preview-image-rendering-design.md` → "Revision — Cycle 12". Decision: ADR-008 in `docs/ai-context/architecture.md`.

---

## File Structure

- `pyproject.toml` — add `pillow>=11.0.0` to `[project.dependencies]`.
- `src/naver_blog_bot/post_generator/models.py` — add `import io`, three module constants, `_resize_image_bytes`, a `max_dim` param on `_image_data_uri`, and pass caps at the photo / meme call sites. CSS and `Draft` schema unchanged.
- `tests/unit/test_draft_html.py` — append Cycle-12 resize tests + small Pillow-based image helpers.

Keep lines ≤88 cols (ruff `E501` is active; there is no `[tool.ruff]` override). Broad `except Exception` is fine (BLE001 not enabled; cli.py already uses it).

---

### Task 1: Add Pillow as a runtime dependency

**Files:**
- Modify: `pyproject.toml` (`[project.dependencies]`)

- [ ] **Step 1: Add the dependency via uv**

Run:
```bash
cd /home/indietogo/projects/naver-blog-bot && uv add 'pillow>=11.0.0'
```
Expected: `uv` resolves, writes `pillow>=11.0.0` into `[project.dependencies]`, updates `uv.lock`, and installs Pillow into the project venv.

- [ ] **Step 2: Verify Pillow imports in the project venv**

Run:
```bash
cd /home/indietogo/projects/naver-blog-bot && uv run python -c "import PIL, PIL.Image, PIL.ImageOps; print('PIL', PIL.__version__)"
```
Expected: prints `PIL 11.x` (or newer). No ImportError.

- [ ] **Step 3: Commit**

```bash
cd /home/indietogo/projects/naver-blog-bot && git add pyproject.toml uv.lock && git commit -m "build: add Pillow dependency for preview image resize (cycle 12)"
```

---

### Task 2: `_resize_image_bytes` helper + constants (TDD)

**Files:**
- Modify: `src/naver_blog_bot/post_generator/models.py` (add `import io`, constants after `_MIME_BY_SUFFIX` at lines 9-15, add helper)
- Test: `tests/unit/test_draft_html.py`

- [ ] **Step 1a: Move all new imports to the TOP import block (avoid ruff E402)**

ruff's default `E` rules include `E402` (imports must be at top of file), so new imports CANNOT be appended mid-file. Replace the existing top import block (lines 1-5) of `tests/unit/test_draft_html.py`:

```python
import base64
from datetime import datetime, timezone
from pathlib import Path

from naver_blog_bot.post_generator.models import Draft
```

with:

```python
import base64
import io
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from naver_blog_bot.post_generator.models import Draft, _EXIF_ORIENTATION_TAG
```

- [ ] **Step 1b: Append the Pillow-based test helpers and the first failing test**

Append to the END of `tests/unit/test_draft_html.py` (helpers/tests are functions, not imports — appending is fine):

```python
def _jpeg_bytes(width: int, height: int) -> bytes:
    # A gradient (not a flat color) so the encoded size is non-trivial.
    base = Image.linear_gradient("L").convert("RGB")
    img = base.resize((width, height))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _animated_gif_bytes() -> bytes:
    frames = [Image.new("P", (12, 12), color=c) for c in (1, 2, 3)]
    buf = io.BytesIO()
    frames[0].save(
        buf, "GIF", save_all=True, append_images=frames[1:], loop=0, duration=80
    )
    return buf.getvalue()


def _embedded_bytes(html: str, css_class: str) -> bytes:
    m = re.search(
        rf'<img class="{css_class}" src="data:[^;]+;base64,([^"]+)"', html
    )
    assert m is not None, f"no <img class={css_class}> data URI in html"
    return base64.b64decode(m.group(1))


def test_resize_shrinks_large_photo(tmp_path: Path) -> None:
    raw = _jpeg_bytes(3000, 2000)
    img = tmp_path / "big.jpg"
    img.write_bytes(raw)
    html = _make_draft(f"[사진: {img}]").to_html()
    embedded = _embedded_bytes(html, "photo")
    assert len(embedded) < len(raw)
    with Image.open(io.BytesIO(embedded)) as out:
        assert max(out.size) <= 1280
```

- [ ] **Step 2: Run it to verify it fails**

Run:
```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_draft_html.py::test_resize_shrinks_large_photo -v
```
Expected: FAIL — `len(embedded) < len(raw)` is false (no resize yet; full 3000×2000 bytes embedded) and/or `max(out.size) <= 1280` false.

- [ ] **Step 3: Add `import io`, constants, and `_resize_image_bytes` to models.py**

In `src/naver_blog_bot/post_generator/models.py`, add `import io` to the import block (after `import base64`):

```python
import base64
import html as _html
import io
import re
```

Then, immediately after the `_MIME_BY_SUFFIX` dict (currently ending at line 15), insert:

```python
_PHOTO_MAX_DIM = 1280
_MEME_MAX_DIM = 480
_JPEG_QUALITY = 82
_EXIF_ORIENTATION_TAG = 0x0112


def _resize_image_bytes(raw: bytes, max_dim: int) -> tuple[bytes, str] | None:
    """Resize/re-encode image bytes for a lighter base64 embed.

    Returns (new_bytes, mime) when smaller, else None (caller keeps the
    original bytes). None on: Pillow missing, decode failure, animated image,
    nothing to do (within cap and unrotated), or re-encode not smaller.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    try:
        with Image.open(io.BytesIO(raw)) as im:
            fmt = (im.format or "").upper()
            if getattr(im, "n_frames", 1) > 1:
                return None  # animated GIF/WebP: preserve original frames
            orientation = im.getexif().get(_EXIF_ORIENTATION_TAG, 1)
            if max(im.size) <= max_dim and orientation == 1:
                return None  # nothing to do; keep original bytes + suffix mime
            oriented = ImageOps.exif_transpose(im)
            if max(oriented.size) > max_dim:
                oriented.thumbnail((max_dim, max_dim))
            out = io.BytesIO()
            if fmt == "PNG":
                oriented.save(out, "PNG", optimize=True)
                mime = "image/png"
            elif fmt == "WEBP":
                oriented.save(out, "WEBP", quality=_JPEG_QUALITY, method=6)
                mime = "image/webp"
            else:
                rgb = oriented if oriented.mode == "RGB" else oriented.convert("RGB")
                rgb.save(out, "JPEG", quality=_JPEG_QUALITY, optimize=True)
                mime = "image/jpeg"
    except Exception:
        return None
    data = out.getvalue()
    if len(data) >= len(raw):
        return None
    return data, mime
```

Note: `fmt` is captured *before* `exif_transpose`, because transpose returns a new image whose `.format` may be `None` (verified against Pillow docs).

- [ ] **Step 4: Wire the helper into `_image_data_uri`**

Replace the current `_image_data_uri` (lines 18-25) with:

```python
def _image_data_uri(path: Path, max_dim: int | None = None) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg")
    if max_dim is not None:
        resized = _resize_image_bytes(raw, max_dim)
        if resized is not None:
            raw, mime = resized
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"
```

- [ ] **Step 5: Pass caps at the two call sites**

In `to_html`, the photo branch — change `uri = _image_data_uri(Path(path))` to:
```python
                uri = _image_data_uri(Path(path), _PHOTO_MAX_DIM)
```

The meme branch — change `uri = _image_data_uri(Path(target)) if target else None` to:
```python
                uri = _image_data_uri(Path(target), _MEME_MAX_DIM) if target else None
```

- [ ] **Step 6: Run the resize test to verify it passes**

Run:
```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_draft_html.py::test_resize_shrinks_large_photo -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/indietogo/projects/naver-blog-bot && git add src/naver_blog_bot/post_generator/models.py tests/unit/test_draft_html.py && git commit -m "feat: resize images before base64 embed in preview HTML (cycle 12)"
```

---

### Task 3: Edge-case tests — upscale guard, EXIF, Pillow-absent, animated, back-compat

**Files:**
- Test: `tests/unit/test_draft_html.py`

- [ ] **Step 1: Add the four edge-case tests**

Append to `tests/unit/test_draft_html.py`:

```python
def test_resize_does_not_upscale_small_image(tmp_path: Path) -> None:
    raw = _jpeg_bytes(100, 80)  # already within the 1280 cap
    img = tmp_path / "small.jpg"
    img.write_bytes(raw)
    html = _make_draft(f"[사진: {img}]").to_html()
    # within cap + no rotation -> original bytes kept, no upscale
    assert _embedded_bytes(html, "photo") == raw


def test_resize_applies_exif_orientation(tmp_path: Path) -> None:
    # Landscape 1600x80 stored with orientation=6 (rotate) -> portrait after transpose.
    exif = Image.Exif()
    exif[_EXIF_ORIENTATION_TAG] = 6
    base = Image.linear_gradient("L").convert("RGB").resize((1600, 80))
    img = tmp_path / "rot.jpg"
    base.save(img, "JPEG", quality=90, exif=exif)
    html = _make_draft(f"[사진: {img}]").to_html()
    embedded = _embedded_bytes(html, "photo")
    with Image.open(io.BytesIO(embedded)) as out:
        assert out.height > out.width  # orientation baked in -> now portrait
        assert max(out.size) <= 1280


def test_resize_falls_back_when_pillow_absent(
    tmp_path: Path, monkeypatch
) -> None:
    raw = _jpeg_bytes(3000, 2000)
    img = tmp_path / "big.jpg"
    img.write_bytes(raw)
    # Simulate Pillow not installed: import inside _resize_image_bytes raises.
    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.setitem(sys.modules, "PIL.Image", None)
    monkeypatch.setitem(sys.modules, "PIL.ImageOps", None)
    html = _make_draft(f"[사진: {img}]").to_html()
    assert '<img class="photo"' in html  # no crash
    assert _embedded_bytes(html, "photo") == raw  # raw bytes embedded (fallback)


def test_resize_preserves_animated_gif_meme(tmp_path: Path) -> None:
    raw = _animated_gif_bytes()
    meme = tmp_path / "anim.gif"
    meme.write_bytes(raw)
    html = _make_draft("[짤방: g1]").to_html({"g1": meme})
    assert "data:image/gif;base64," in html
    assert _embedded_bytes(html, "meme") == raw  # frames preserved (passthrough)
```

_EXIF orientation 6 = rotate; `ImageOps.exif_transpose` swaps the axes so a stored 1600×80 becomes ~80×1600, then `thumbnail(1280)` keeps it portrait. `Image`, `io`, `re`, `sys`, and `_EXIF_ORIENTATION_TAG` were already imported at the top in Task 2 Step 1a — no new imports here._

- [ ] **Step 2: Run the new edge-case tests**

Run:
```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_draft_html.py -v -k "resize"
```
Expected: all 5 `resize` tests PASS (shrink, no-upscale, exif, pillow-absent, animated-gif).

- [ ] **Step 3: Run the FULL existing suite for back-compat**

Run:
```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_draft_html.py -v
```
Expected: all original 12 tests + 5 new tests PASS. In particular `test_to_html_jpeg_mime` and `test_to_html_embeds_real_photo_as_base64` still pass: the 1×1 fixtures are within cap and unrotated, so `_resize_image_bytes` returns `None` (skip path) and the original bytes + suffix-derived MIME are preserved.

- [ ] **Step 4: Commit**

```bash
cd /home/indietogo/projects/naver-blog-bot && git add tests/unit/test_draft_html.py && git commit -m "test: cover resize edge cases (upscale guard, EXIF, no-Pillow, animated) (cycle 12)"
```

---

### Task 4: Real smoke (12-photo HTML size) + full gate + plan close

**Files:**
- (No source edits; verification only)

- [ ] **Step 1: Record the BEFORE state (photo sizes + prior HTML if present)**

Run:
```bash
cd /home/indietogo/projects/naver-blog-bot && du -ch sim/photos/spoglia/meet*.jpg | tail -1 && ls -l drafts/draft-20260531-140300.html 2>/dev/null || echo "no prior html"
```
Expected: prints the total size of the 12 source photos (the spec assumes ~7MB each / ~84MB+) and any existing HTML size for comparison.

- [ ] **Step 2: Regenerate both spoglia previews with the resize code**

Run:
```bash
cd /home/indietogo/projects/naver-blog-bot && uv run naver-bot preview draft-20260531-140300 && uv run naver-bot preview draft-20260531-140749
```
Expected: each writes `drafts/<id>.html` without error. (On WSL the browser-open step may print an `explorer.exe` notice; that is non-fatal by design.)

- [ ] **Step 3: Measure the resulting HTML sizes**

Run:
```bash
cd /home/indietogo/projects/naver-blog-bot && ls -l drafts/draft-20260531-140300.html drafts/draft-20260531-140749.html && python3 -c "import os;[print(p, round(os.path.getsize(p)/1048576,2),'MB') for p in ['drafts/draft-20260531-140300.html','drafts/draft-20260531-140749.html']]"
```
Expected: each HTML < 8 MB (target < 5 MB). Record the actual numbers. If a file is ≥ 8 MB, lower `_PHOTO_MAX_DIM` to 1080 in models.py, re-run, and re-measure before proceeding.

- [ ] **Step 4: Confirm images still embed (img count ≥ photos)**

Run:
```bash
cd /home/indietogo/projects/naver-blog-bot && grep -c '<img class="photo"' drafts/draft-20260531-140300.html
```
Expected: ≥ 12 (one `<img>` per photo marker; still real renders, not placeholders).

- [ ] **Step 5: Run the full project gate**

Run:
```bash
cd /home/indietogo/projects/naver-blog-bot && bash scripts/check.sh; echo "RC=$?"
```
Expected: ruff check clean, ruff format --check clean, full pytest green, `RC=0`. (Do NOT trust a green tail without `RC=0` — NOBV-002.) If ruff format flags models.py/tests, run `uv run ruff format .`, re-stage, and amend the relevant commit.

- [ ] **Step 6: Commit any formatting/tuning + leave the smoke artifacts untracked**

```bash
cd /home/indietogo/projects/naver-blog-bot && git status --short
```
The `drafts/*.html` are gitignored (personal data) — do not commit them. Commit only source/format changes if Step 5 required `ruff format`.

---

## Verification Summary (maps to spec "Verification (Cycle 12)")

- Large source + cap → embedded bytes strictly smaller, decoded longest edge ≤ cap → `test_resize_shrinks_large_photo`.
- Within cap → original bytes kept (no upscale) → `test_resize_does_not_upscale_small_image`.
- EXIF-oriented source → output reflects orientation → `test_resize_applies_exif_orientation`.
- Pillow absent → raw URI, no crash, equals no-resize encoding → `test_resize_falls_back_when_pillow_absent`.
- Animated GIF meme → original bytes preserved → `test_resize_preserves_animated_gif_meme`.
- Back-compat → original 12 `to_html` tests pass → Task 3 Step 4.
- Real smoke → 12-photo HTML drops from ~103MB to <8MB (target <5MB), `<img>` count ≥ photos → Task 4 Steps 1-4.
- `bash scripts/check.sh` RC=0 → Task 4 Step 5.
