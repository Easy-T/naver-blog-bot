# Design: Preview Image Resize — Multi-frame Still vs Genuine Animation

**Date:** 2026-06-08
**Subsystem:** `post_generator` preview image rendering
**Status:** approved-by-goal
**Sources:** `sim/goal-fix-mpo-downscale.md`, ADR-008 in `docs/ai-context/architecture.md`, Pillow docs for `Image.n_frames`, `Image.is_animated`, `MpoImageFile.seek()`

## Problem

`Draft.to_html()` embeds photos and memes as base64 data URIs for local preview. ADR-008 added Pillow-based resizing before embedding, but `_resize_image_bytes()` currently treats every image with `n_frames > 1` as an animation and returns `None`, causing callers to embed original bytes.

That predicate is too broad. iPhone MPO files are multi-frame image containers but are used here as still photos. Pillow reports them as `format == "MPO"`, `n_frames > 1`, and `is_animated == True`, so the existing guard skips downscaling and produces very large preview HTML.

## Domain Boundary

- **멀티프레임 정지영상:** A multi-frame/page image whose preview representation is a representative still frame. MPO is the primary case. These should be downscaled.
- **진짜 애니메이션 짤방:** A GIF/WebP meme whose temporal frame sequence is the content. These must remain byte-identical so frames are preserved.

`n_frames` and `is_animated` alone are not sufficient domain signals because both can be true for MPO and genuine animations. The reliable boundary for this project is image format.

## Decision

Inside `_resize_image_bytes(raw, max_dim)`:

1. Keep `fmt = (im.format or "").upper()` as the format signal.
2. Preserve original bytes only when `fmt in {"GIF", "WEBP"}` and `getattr(im, "is_animated", False)` is true.
3. For all other `n_frames > 1` images, call `im.seek(0)` and continue the existing EXIF transpose, thumbnail, format-preserving re-encode, and never-bigger check.
4. Update the docstring from generic “animated image” to “genuine animated GIF/WebP”.

No size warning/failure guard is added. No CLI, storage, data-flow, or dependency changes are made.

## Components and Data Flow

Existing flow remains unchanged:

`preview_command` → `Draft.to_html(meme_paths)` → `_image_data_uri(path, max_dim)` → `_resize_image_bytes(raw, max_dim)`

- Photo markers use `_PHOTO_MAX_DIM = 1280`.
- Meme markers use `_MEME_MAX_DIM = 480`.
- Missing files and decode failures keep existing graceful fallback behavior.

## Testing Requirements

Use TDD in `tests/unit/test_draft_html.py`:

1. Add an MPO fixture and a failing test proving a multi-frame still photo is embedded smaller than the raw MPO and has max dimension ≤1280.
2. Replace the existing false-safety GIF animation fixture/test with a genuine multi-frame GIF fixture larger than the meme cap, asserting byte-identical preservation.
3. Add a genuine multi-frame WEBP fixture larger than the meme cap, asserting byte-identical preservation.
4. Run the full check gate and `sim/measure_muto_html.py` to verify the real `Draft.to_html()` path shrinks the 28-photo muto preview below roughly 15 MB.

## Non-goals

- Do not add preview HTML size warnings, hard limits, or exceptions.
- Do not add a TIFF-specific test in this cycle.
- Do not change image caps, JPEG/WebP quality, MIME suffix handling, or CLI preview behavior.
- Do not refactor adjacent rendering code.

## ADR Assessment

ADR-012 records the corrected interpretation of ADR-008's animation passthrough rule. The preview resize architecture remains the same, but the append-only architecture log needed an explicit refinement because ADR-008 described the old `n_frames > 1` predicate.
