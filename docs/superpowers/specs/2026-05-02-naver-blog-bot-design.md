# naver-blog-bot Design Spec

Created: 2026-05-02
Project: naver-blog-bot

## 1. Goal

`naver-blog-bot` automates the path from photos plus a short memo to a Naver Blog post that resembles the owner's writing style and can be uploaded to the owner's Naver Blog.

The primary use case is writing review posts for 체험단 campaigns, such as 포포몬 체험단. The tool should reduce repetitive drafting and publishing work while preserving the author's tone, common visual habits, and publishing control.

Success is not just syntactic generation. A generated draft is acceptable only when the owner can review it and judge that it feels like something they would have written.

## 2. Target Blog Context

- Blog URL: https://blog.naver.com/flowerbend
- The owner has OGQ emoticons available.
  - artworkId: `644e042a7d7f8`
  - Name/context: 세루리안
- The owner often uses 짤방, meaning short reaction images or meme-like visual inserts.
- Naver two-factor authentication is currently OFF.

## 3. Product Phases

### Phase 1: Claude Code Conversation-Based CLI

Phase 1 is the current target. The user operates the system through a local CLI built and iterated on inside Claude Code.

The CLI should support:

- Initial login/profile setup
- Style profile refresh from the owner's blog writing
- Meme library construction
- Draft generation from photos and memo
- Draft preview
- Controlled publishing to Naver Blog

### Phase 2: Telegram Bot

Phase 2 is deferred until Phase 1 is proven. The Telegram bot should reuse the Phase 1 modules rather than reimplementing scraping, style profiling, generation, storage, or publishing logic.

Phase 1 should therefore keep boundaries clean enough that a future Telegram interface can call the same application services.

## 4. Architecture Approach

Use modular CLI architecture, referred to in prior brainstorming as Approach B.

Top-level modules:

- `style_profiler`
- `meme_library`
- `post_generator`
- `naver_publisher`
- `shared/claude_client.py`

The CLI coordinates these modules but should not contain the core domain logic itself.

## 5. Module Responsibilities

### 5.1 `style_profiler`

Purpose: learn the owner's writing style from existing Naver Blog posts.

Responsibilities:

- Scrape or collect the owner's existing blog posts.
- Extract representative style signals using Claude.
- Produce a durable style profile stored as JSON.
- Support periodic refresh through the CLI.

The style profile should capture reusable writing traits such as:

- Common post structure
- Sentence length tendencies
- Tone and emotional pacing
- Frequently used expressions
- Review-post conventions
- Product-experience storytelling pattern
- How photos, emoticons, and 짤방 are typically integrated

### 5.2 `meme_library`

Purpose: build a searchable local library of the owner's 짤방.

Responsibilities:

- Extract or import reaction images used by the owner.
- Store images under `assets/memes/`.
- Use Claude Vision to automatically tag images.
- Produce a JSON index that can be used during post generation.

Tags should describe when the image is useful, not only what the image contains. Examples include surprise, satisfaction, disappointment, anticipation, cuteness, food reaction, product reveal, and comedic emphasis.

### 5.3 `post_generator`

Purpose: generate draft blog posts from photos, a short memo, the style profile, and relevant meme candidates.

Responsibilities:

- Accept photo paths and a user memo.
- Load the current style profile.
- Retrieve relevant few-shot examples by category.
- Retrieve appropriate meme candidates.
- Call Claude API to generate a draft.
- Use prompt caching to reduce repeated context cost.
- Save generated drafts to `drafts/` as reviewable local artifacts.

The generator should not directly publish. It produces drafts only.

### 5.4 `naver_publisher`

Purpose: automate Naver Blog SmartEditor using Playwright.

Responsibilities:

- Use a persistent Playwright Chromium profile.
- Check whether the Naver session is valid before publishing.
- Stop and request user intervention if login, CAPTCHA, or session recovery is needed.
- Open SmartEditor and insert the draft content.
- Upload photos after stripping EXIF metadata.
- Insert OGQ emoticons when requested and available.
- Insert selected 짤방 images.
- Publish to the target category or visibility setting.

SmartEditor selectors should be centralized in `naver_publisher/selectors.py` so DOM changes are isolated.

### 5.5 `shared/claude_client.py`

Purpose: centralize Claude API usage.

Responsibilities:

- Configure the Anthropic SDK.
- Provide prompt-caching-aware request helpers.
- Keep model and timeout configuration in one place.
- Avoid scattering raw Claude API calls across modules.

## 6. Technology Stack

- Python 3.11+
- `uv` for environment and dependency management
- Playwright with Chromium and persistent user profile
- Claude API through the `anthropic` SDK
- Prompt caching for repeated style/profile/few-shot context
- Typer for CLI commands
- `pydantic-settings` for configuration
- JSON file storage instead of a database

No database is planned for Phase 1. JSON is sufficient because local state is small, single-user, and mostly append-or-refresh style data.

## 7. Planned Project Structure

```text
naver-blog-bot/
├── pyproject.toml
├── src/naver_blog_bot/
│   ├── cli.py
│   ├── config.py
│   ├── style_profiler/
│   ├── meme_library/
│   ├── post_generator/
│   ├── naver_publisher/
│   └── shared/claude_client.py
├── config/
├── assets/memes/
├── drafts/
├── browser-profile/
├── tests/
│   ├── unit/
│   └── integration/
└── docs/
```

The following paths should be gitignored because they contain local state, generated artifacts, personal data, or browser session data:

- `config/style_profile.json`
- `config/meme_index.json`
- `assets/memes/`
- `drafts/`
- `browser-profile/`
- local environment and secret files

## 8. CLI Commands

### `naver-bot init`

Initial one-time setup.

Expected behavior:

- Launch Chromium with persistent Playwright profile.
- Let the user manually log into Naver.
- Store the authenticated browser profile under `browser-profile/`.
- Verify that the session is usable.

### `naver-bot profile-refresh`

Refresh the style profile.

Expected behavior:

- Read recent or representative posts from the owner's blog.
- Extract style traits with Claude.
- Save the refreshed profile to `config/style_profile.json`.

### `naver-bot meme-build`

Build or refresh the meme library.

Expected behavior:

- Collect or scan available 짤방 images.
- Tag them with Claude Vision.
- Save the index to `config/meme_index.json`.

### `naver-bot draft <photos> "메모"`

Generate a local draft.

Expected behavior:

- Accept one or more photo paths.
- Accept a short Korean memo.
- Load style profile and relevant examples.
- Select relevant meme candidates.
- Generate the post draft with Claude.
- Save the draft under `drafts/` with a draft ID.

### `naver-bot preview <draft_id>`

Preview a generated draft.

Expected behavior:

- Render the draft content locally in a readable format.
- Show selected photos, OGQ/emoticon placeholders, and meme insertions.
- Allow the user to inspect before publishing.

### `naver-bot publish <draft_id>`

Publish a reviewed draft.

Expected behavior:

- Load the selected draft.
- Confirm session state.
- Stop for user intervention if login or CAPTCHA is required.
- Upload content into Naver SmartEditor.
- Insert OGQ emoticons and 짤방 where possible.
- Publish according to the configured visibility/category.

Publishing is the only command that mutates external state.

## 9. Style Learning Strategy

Use a hybrid style learning approach:

1. Extracted style profile
2. Category-specific few-shot examples, typically 2-3 representative posts

The style profile provides stable high-level guidance. Few-shot examples provide concrete phrasing, pacing, formatting, and category-specific conventions.

For 체험단 후기, few-shot examples should reflect review-specific structure, such as:

- Why the product/service was tried
- First impression
- Detailed experience
- Photos and observations
- Pros and personal reactions
- Natural closing recommendation or caveat

## 10. Login and Session Strategy

Use Playwright persistent Chromium profile stored under `browser-profile/`.

Initial login is manual:

1. User runs `naver-bot init`.
2. Browser opens.
3. User logs into Naver manually.
4. Tool stores browser session state in the persistent profile.

Because two-factor authentication is OFF, this should be stable enough for Phase 1.

If CAPTCHA appears, the automation must stop and notify the user. The system must not bypass CAPTCHA or implement evasion logic.

If the session expires, publishing should stop before modifying the editor and ask the user to re-login.

## 11. Publishing Constraints

The system is intended for the owner's own account only.

Operational constraints:

- Use reasonable publishing frequency, currently expected around 2-3 posts per week or less.
- Do not automate CAPTCHA bypass.
- Do not mass-post.
- Do not use the tool for third-party accounts.
- Keep user review in the loop before publishing.

## 12. Privacy and Safety

Photos may contain EXIF metadata. Before upload, the publisher should strip EXIF metadata from images.

Local paths that may contain personal content should be gitignored.

Secrets and credentials should not be committed. Authentication should rely on the local Playwright browser profile rather than storing the Naver password in project files.

## 13. Risks and Responses

### Naver SmartEditor DOM changes

Risk: Playwright selectors break when Naver changes SmartEditor DOM.

Response:

- Centralize selectors in `naver_publisher/selectors.py`.
- Keep publisher integration tests or smoke checks focused on selector validity where possible.

### CAPTCHA

Risk: Naver presents CAPTCHA during login or publishing.

Response:

- Stop automation.
- Tell the user manual intervention is required.
- Do not bypass or evade CAPTCHA.

### Session expiration

Risk: The persistent browser profile becomes logged out.

Response:

- Check session at the start of publishing.
- Ask the user to rerun login flow when needed.

### Claude API cost

Risk: Repeated style profile and few-shot context increases API cost.

Response:

- Use prompt caching for stable context.
- Keep large reusable context in cacheable prompt blocks.

### OGQ insertion failure

Risk: OGQ emoticon insertion may fail due to UI changes or availability issues.

Response:

- Prefer OGQ when available.
- Fall back to normal emoji if insertion fails.
- Preserve draft publishability even when OGQ insertion is unavailable.

### Photo metadata leakage

Risk: Uploaded photos may include EXIF metadata.

Response:

- Strip EXIF before upload.
- Use processed temporary images for publisher upload.

### Terms of service and account safety

Risk: Automation may violate platform expectations if used aggressively.

Response:

- Restrict use to the owner's account.
- Keep reasonable frequency.
- Keep manual review before publish.

## 14. Phase 1 Completion Criteria

Phase 1 is complete when all of the following are true:

- `naver-bot init` works and stores a usable persistent login profile.
- `naver-bot profile-refresh` produces a style profile.
- `naver-bot meme-build` produces a tagged meme library.
- 5 photos plus a short memo can generate a draft.
- The generated draft can be previewed.
- A post can be published to a private category with OGQ emoticon and 짤방 included.
- The owner reviews at least one generated post and judges it as "내가 쓴 것 같다".

## 15. Out of Scope for Phase 1

- Telegram bot interface
- Multi-user support
- Database-backed storage
- Scheduling or bulk publishing
- CAPTCHA bypass
- Third-party account publishing
- Full web dashboard
- Fully autonomous publish without user review

## 16. Self-Review

- Scope check: The spec describes Phase 1 CLI and defers Telegram bot to Phase 2.
- Safety check: CAPTCHA bypass, mass posting, third-party account use, and autonomous publishing are explicitly out of scope.
- Architecture check: The four main modules plus shared Claude client map to the requested modular CLI design.
- Storage check: JSON storage is preserved; no database is introduced.
- Stack check: Python 3.11+, uv, Playwright, Anthropic SDK, Typer, pydantic-settings, and JSON storage are included.
- Completion check: Phase 1 completion criteria include draft generation, preview, private publish, OGQ, 짤방, and owner style judgment.
