# Design Spec: Preview Image Rendering + WSL Browser Open

**RPI-Cycle:** 11
**Date:** 2026-05-31

## Problem
`Draft.to_html()` renders `[사진: path]` and `[짤방: meme_id]` markers as gray
placeholder `<div>`s, not actual images. Opening the HTML in a Windows browser
shows only boxes — the draft cannot serve its purpose as a visual preview.
Additionally, `preview` calls `webbrowser.open()` which fails on WSL (no GUI
browser), printing a wall of `xdg-open: ... not found` errors.

## Goal
The HTML preview must be a **self-contained, visually complete draft** that
shows real photos and memes, openable from Windows.

## Decisions
- **Image embedding: base64 data URI** (user choice). Each `[사진: path]` and
  resolved `[짤방: meme_id]` becomes `<img src="data:{mime};base64,...">`. The
  HTML is self-contained — works when opened from anywhere, no path/WSL
  dependency.
- **Meme id resolution:** `to_html()` gains an optional
  `meme_paths: dict[str, Path] | None = None` param. `preview_command` builds
  the map from `load_meme_index(settings.meme_index_path)` (`{m.id: m.path}`)
  and passes it. Keeps `Draft` (post_generator) decoupled from meme_library —
  no new import in models.py.
- **Graceful fallback:** if a photo file is missing, or a meme id is unknown /
  its file missing, keep the existing placeholder `<div>` (so a draft authored
  before files exist still previews, just without that image).
- **WSL open:** in `preview_command`, detect WSL; if so, open via
  `explorer.exe` against the Windows-visible path instead of `webbrowser`.
  Pillow is NOT available and is NOT required (raw `<img>`, no resize/EXIF).

## Scope
- `src/naver_blog_bot/post_generator/models.py` — `to_html()` only.
  - New helper to read a file → `data:` URI (mime by suffix:
    .jpg/.jpeg→image/jpeg, .png→image/png, .gif→image/gif, .webp→image/webp;
    default image/jpeg).
  - `[사진: path]` → `<img>` if file exists, else current placeholder.
  - `[짤방: id]` → resolve via `meme_paths`, `<img>` if file exists, else
    current placeholder.
  - Signature: `to_html(self, meme_paths: dict[str, Path] | None = None)`.
    Default `None` preserves existing callers/tests (placeholder behavior).
- `src/naver_blog_bot/cli.py` — `preview_command` only.
  - Build `meme_paths` from meme_index, pass to `to_html`.
  - WSL-aware open: try `explorer.exe <path>` on WSL; keep `webbrowser.open`
    elsewhere; never crash on open failure (clipboard step must still run).

## Out of Scope
- Pillow / image resize / EXIF rotation.
- Changing marker syntax or the generator.
- OGQ emoticon rendering (stays as badge).
- publish command.
- Changing draft JSON schema.

## Verification
- Unit: `to_html(meme_paths=...)` with a real temp image emits
  `data:image/...;base64,` and an `<img`; missing file → placeholder retained.
- Unit: unknown meme id → placeholder retained.
- Unit: default `to_html()` (no arg) still emits placeholders (back-compat).
- Real smoke: regenerate spoglia food+love HTML, confirm `<img` count ≥ photos,
  copy to Windows, user confirms images visible.
- `bash scripts/check.sh` green (ruff + full pytest).

---

## Revision — Cycle 12 (2026-06-06): Resize Images Before Embedding

**Supersedes** the Cycle 11 decision "Pillow is NOT available and is NOT required
(raw `<img>`, no resize/EXIF)" and the Out-of-Scope line "Pillow / image resize /
EXIF rotation". Rationale: Cycle 11 base64-embeds full-resolution photo bytes, so a
12-photo draft produces a ~103MB self-contained HTML — too heavy to open as a draft.
Recorded as ADR-008 in `docs/ai-context/architecture.md`.

### Approaches considered
1. **Format-preserving Pillow resize before base64** (chosen) — decode, orient,
   downscale, re-encode in the same format. Biggest win on the dominant full-res
   JPEG-photo case; preserves PNG transparency and animated GIFs.
2. Force every image to JPEG — smaller still, but destroys PNG transparency and GIF
   animation. Rejected.
3. CSS-only / no embed change — does not reduce bytes (CSS already caps *display*
   width; the 103MB is the encoded *bytes*). Rejected — doesn't solve the problem.

### New Decisions
- **Pillow becomes a required dependency** (`pillow>=11.0.0` in pyproject
  `dependencies`). Recorded as ADR-008.
- **Resize before base64.** `_image_data_uri(path, max_dim=None)` gains an optional
  `max_dim`. A new `_resize_image_bytes(raw, max_dim)` helper decodes with Pillow,
  applies `ImageOps.exif_transpose` (bake orientation into pixels), downscales the
  longest edge to `max_dim` via `Image.thumbnail` (never upscales), and re-encodes
  format-preserving (JPEG→JPEG q82, PNG→PNG optimize, WEBP→WEBP q82; any other
  decoded format → JPEG).
- **Caps (module constants):** photos `_PHOTO_MAX_DIM = 1280`; memes
  `_MEME_MAX_DIM = 480` (display widths are 720px / 200px → ~1.8× / 2.4× density).
  JPEG quality `_JPEG_QUALITY = 82`.
- **Animated images preserved.** If `n_frames > 1` (animated GIF/WebP), skip
  re-encode and keep the original bytes (resizing animations is out of scope and
  would drop frames). Memes are often animated GIFs.
- **Never-bigger guard.** If the re-encoded result is not strictly smaller than the
  source bytes, keep the source (handles already-small images; guarantees no bloat;
  preserves Cycle 11 back-compat for tiny test fixtures).
- **Graceful fallback (unchanged contract).** If Pillow is absent (ImportError) or
  decode fails (any exception), `_resize_image_bytes` returns None and the caller
  embeds the raw bytes — the Cycle 11 behavior. Never crashes.

### Scope (Cycle 12)
- `src/naver_blog_bot/post_generator/models.py` — add `import io`, the three module
  constants, `_resize_image_bytes`, a `max_dim` param on `_image_data_uri`, and pass
  `_PHOTO_MAX_DIM` / `_MEME_MAX_DIM` at the photo / meme call sites. CSS unchanged.
- `pyproject.toml` — add `pillow>=11.0.0` to `dependencies`.
- `docs/ai-context/architecture.md` — ADR-008 (append-only).

### Still Out of Scope (Cycle 12)
- Changing marker syntax, the generator, or the draft JSON schema.
- OGQ emoticon rendering; the publish command; CSS layout changes.
- Resizing/transcoding animated frames; AVIF.

### Verification (Cycle 12)
- Unit: a large source image + `max_dim` → embedded bytes strictly smaller than the
  source file and decoded longest edge ≤ `max_dim`.
- Unit: a source already ≤ `max_dim` → original bytes kept (no upscale; guard holds).
- Unit: an EXIF-oriented source → output reflects the applied orientation.
- Unit: Pillow absent (monkeypatched ImportError) → raw-bytes URI, no crash, equal to
  the no-resize encoding.
- Unit: an animated GIF meme → original bytes preserved (passthrough).
- Back-compat: the Cycle 11 `to_html` tests still pass.
- Real smoke: regenerate the 12-photo spoglia food+love HTML; total size drops from
  ~103MB to <8MB (target <5MB); images still render when opened in Windows.
- `bash scripts/check.sh` green (ruff + format --check + full pytest, RC=0).
