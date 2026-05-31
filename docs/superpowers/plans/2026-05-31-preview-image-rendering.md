**Status:** completed
**RPI-Cycle:** 11
**Started:** 2026-05-31
**Completed:** 2026-06-01

# Plan: Preview Image Rendering + WSL Browser Open

Spec: `docs/superpowers/specs/2026-05-31-preview-image-rendering-design.md`

Implementation: execute-strict direct (small cycle, 2 files). TDD per task.

## Task 1 — `to_html()` renders real images via base64 (models.py)

**Files:** `src/naver_blog_bot/post_generator/models.py`,
`tests/unit/test_draft_html.py`

Steps:
- [x] Add module-level helper `_image_data_uri(path: Path) -> str | None`:
      returns `data:{mime};base64,{b64}` reading bytes; mime by suffix map
      (.jpg/.jpeg→image/jpeg, .png→image/png, .gif→image/gif, .webp→image/webp,
      else image/jpeg); returns `None` if file missing / unreadable.
- [x] Change signature to
      `to_html(self, meme_paths: dict[str, Path] | None = None) -> str`.
- [x] `[사진: path]`: if `_image_data_uri(Path(path))` is not None → emit
      `<img class="photo" src="{uri}" alt="...">`; else keep existing
      `photo-placeholder` div.
- [x] `[짤방: id]`: look up id in `meme_paths` (default empty dict); if found and
      `_image_data_uri` not None → emit `<img class="meme">`; else keep
      existing `meme-placeholder` div.
- [x] Add CSS for `img.photo`/`img.meme`.

**Tests (write first):**
- [x] real temp PNG via `[사진: <tmp>]` → output contains `data:image/png;base64,`
      and `<img`.
- [x] `[사진: /nonexistent.jpg]` → output retains `photo-placeholder`.
- [x] `[짤방: m1]` with `meme_paths={"m1": <tmp png>}` → `<img` + base64.
- [x] `[짤방: unknown]` with empty map → retains `meme-placeholder`.
- [x] `to_html()` with no arg + missing files → placeholders (back-compat).

**Verify:** `pytest tests/unit/test_draft_html.py -q` → 6 passed. ✅

## Task 2 — preview passes meme_paths + WSL-aware open (cli.py)

**Files:** `src/naver_blog_bot/cli.py`, `tests/unit/test_cli.py`

Steps:
- [x] In `preview_command`, after loading draft: build
      `meme_paths = {m.id: m.path for m in load_meme_index(settings.meme_index_path).memes}`
      and call `draft.to_html(meme_paths)`.
- [x] Add helper `_open_in_browser(html_path: Path) -> None`: WSL detect via
      `/proc/version`, `explorer.exe`; else `webbrowser.open`. Never raise.
- [x] Replace `webbrowser.open(...)` with `_open_in_browser(html_path)`.
- [x] Keep clipboard logic; ensure it runs regardless of open result.

**Tests (write first):**
- [x] `preview` produces HTML containing `<img` when meme_index has the id
      (`test_preview_embeds_meme_image`).
- [x] open failure does not crash (`test_open_in_browser_swallows_failures`).

**Verify:** `pytest tests/unit/test_cli.py -q` → 27 passed. ✅

## Task 3 — Real smoke + closeout prep

- [x] Regenerate spoglia food + love HTML via `preview`.
- [x] Assert `<img` occurrences ≥ 12 (photos) + memes present.
      → both: 12 photo `<img>` + 3 meme `<img>` = 15 data URIs, 0 real placeholders.
- [x] Copy both HTML to Windows; user confirms images visible. ✅ (user: "보임 - 성공")
- [x] `bash scripts/check.sh` green. ✅ "All checks passed"
- [x] Closeout (this document + state.json cycle 11 + ADR-007).

## Outcome
Preview HTML is now a self-contained visual draft: real photos + memes embedded
as base64 `<img>`, openable from Windows; `preview` opens via `explorer.exe` on
WSL and never crashes on open failure. Back-compat preserved (default no-arg
`to_html()` keeps placeholders).

## Follow-up (next cycle)
- **Cycle 12 — image resize:** base64 of 12×7MB photos → ~103MB HTML. User chose
  to add a Pillow-based resize pass (e.g. cap width ~1080px) to cut file size by
  10–50×. Deferred here by explicit decision; tracked as the next RPI cycle.

## Risks (realized)
- Large base64 confirmed: ~103MB per HTML. Functional but heavy; → Cycle 12.
- explorer.exe open: non-fatal by design; verified swallows failures.
