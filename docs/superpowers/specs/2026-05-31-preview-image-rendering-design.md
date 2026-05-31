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
