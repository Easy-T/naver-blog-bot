# Design Spec: Paste-Ready SmartEditor Export

**RPI-Cycle:** 13
**Date:** 2026-06-06
**Subsystem:** post_generator / preview (paste-text export — distinct concern from
the image-rendering spec `2026-05-31-preview-image-rendering-design.md`)

## Problem

`naver-bot preview` copies `draft.body_markdown` to the clipboard **verbatim**
(`cli.py` `preview_command`). The body still contains generator markers:

- `[사진: /home/indietogo/.../IMG_1234.jpg]` (own line)
- `[짤방: meme_id]` (own line)
- `{{이모티콘:감정유형}}` (inline)
- markdown headings `# / ## / ###`

Pasting that into the Naver SmartEditor dumps raw markers — including the
**absolute WSL photo path** — which the user must hand-delete. The rendered HTML
preview shows the images but cannot be pasted as clean editor text. So the daily
loop (draft → preview → paste into SmartEditor → manually upload photos/memes)
has no clean, pasteable text artifact.

## Goal

`preview` must produce **paste-ready text** for the SmartEditor: the prose with
each marker rewritten as a short human-readable *insertion cue*, so the user
pastes once and only has to upload the photos/memes/emoticons by hand at the
marked spots. No absolute paths leak.

## Decisions

- **New method `Draft.to_paste_text(meme_labels: dict[str, str] | None = None)
  -> str`** — a sibling of `to_html`. Line-based dispatch mirrors `to_html`'s
  parser so both stay consistent.
- **Decoupling preserved (refines ADR-007).** `to_paste_text` takes a plain
  `dict[str, str]` (meme id → human label), NOT a `MemeIndex`. `models.py` keeps
  zero `meme_library` imports. `cli.preview_command` builds the label map.
- **Marker → cue conversion** (cues use 〔…〕 / U+3014,U+3015 brackets so they are
  visually distinct from the `[...]`/`{{...}}` markers and read clearly as plain
  text):
  - `[사진: <abs path>]` → `〔📷 사진 삽입: <basename>〕` via `Path(p).name`.
    Absolute path never appears in output.
  - `[짤방: <id>]` → `〔🖼️ 짤방: <label>〕` where `label = meme_labels[id]` if
    present, else the raw `id` (fallback when no index / unknown id).
  - `{{이모티콘:<유형>}}` → `〔😊 이모티콘: <유형>〕` (inline; multiple per line
    supported), reusing the same `\{\{이모티콘:([^}]+)\}\}` pattern as `to_html`.
  - Headings `# / ## / ###` → the heading text as a plain line (leading hashes
    stripped); SmartEditor applies its own styling.
  - Plain paragraphs and blank lines → preserved as-is (blank lines kept so
    paragraph breaks survive the paste).
- **`preview` writes `drafts/<draft_id>.txt`** with the paste-text AND copies the
  same paste-text to the clipboard (instead of raw `body_markdown`). The `.txt`
  is the durable fallback: on WSL the clipboard often fails (no xclip/xsel), and
  without it the user would have no pasteable artifact at all.
- **Graceful paths unchanged.** Clipboard copy stays best-effort: `pyperclip`
  absent or `copy()` raising still prints the existing guidance and never
  crashes. The `.txt` write happens before the clipboard step so a clipboard
  failure still leaves a usable file.

## Components

- `src/naver_blog_bot/post_generator/models.py`
  - Add `Draft.to_paste_text(meme_labels=None) -> str`.
  - Reuse the existing inline-emoticon regex; add a small helper or inline the
    line dispatch. No change to `to_html`, `_image_data_uri`, or
    `_resize_image_bytes`.
- `src/naver_blog_bot/cli.py` — `preview_command` only.
  - Build `meme_labels = {m.id: (", ".join(m.tags) if m.tags else (m.alt_text or
    m.id)) for m in index.memes}`.
  - `paste_text = draft.to_paste_text(meme_labels)`.
  - Write `settings.drafts_dir / f"{draft_id}.txt"` = paste_text (UTF-8).
  - Copy `paste_text` (not `body_markdown`) to clipboard; keep graceful fallback
    messages, mentioning the saved `.txt` path.

## Data Flow (changed step)

Old step 8: `preview` writes `<id>.html`, opens browser, copies
`body_markdown` to clipboard.
New step 8: `preview` writes `<id>.html` (unchanged), writes `<id>.txt`
(paste-text), opens browser, copies **paste-text** to clipboard.

## Error Handling

- Unknown meme id / no `meme_labels` → cue falls back to the raw id (no crash).
- Missing photo file → still produce the basename cue (paste-text is about
  placement, not file existence; mirrors that the user uploads manually anyway).
- Clipboard unavailable → `.txt` already written; print guidance pointing at it.

## Testing

- Unit (`Draft.to_paste_text`):
  - All three markers + a heading + a plain paragraph in one body →
    (a) output contains none of `[사진:`, `[짤방:`, `{{이모티콘:`;
    (b) no absolute path — `/home/` not in output;
    (c) meme cue uses the label when `meme_labels` given;
    (d) meme cue falls back to id when label absent;
    (e) emoticon 유형 preserved in the cue;
    (f) heading text present without leading `#`; plain paragraph preserved.
  - Multiple emoticons on one line → both converted.
  - Marker-free body → no `〔` cues introduced; text lines preserved (idempotent
    in the sense that running it again yields the same output).
- Unit (cli `preview_command`, with mocked draft/meme index):
  - Writes `<id>.txt` whose content == `draft.to_paste_text(labels)`.
  - Clipboard receives paste-text, not `body_markdown` (assert no raw marker in
    the copied value).
- Back-compat: existing `to_html` / image tests unchanged and green.
- `bash scripts/check.sh` RC=0 (ruff check + ruff format --check + full pytest);
  verify the "passed" token AND RC explicitly (NOBV-002 — no false green).

## Out of Scope

- Changing marker syntax or the generator.
- OGQ artwork rendering (`Draft.ogq_artwork_id` stays out of the body, as in
  `to_html`).
- Rich-text/HTML clipboard (SmartEditor paste is plain text here).
- Changing the draft JSON schema or `to_html`.
- The publish command.

## Decision Record

Recorded as **ADR-009** in `docs/ai-context/architecture.md` (Refines ADR-007):
the preview clipboard contract changes from raw `body_markdown` to transformed
paste-text, and a new `drafts/<id>.txt` artifact is introduced.
