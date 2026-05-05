# Profile Refresh Design Spec

Created: 2026-05-04
Project: naver-blog-bot
Cycle: profile-refresh

## 1. Goal

Implement the first usable `naver-bot profile-refresh` slice by extracting writing-style traits from user-provided local sample post files and saving them as named style profiles.

The feature should let the user maintain multiple writing profiles, such as `default`, `food-review`, `product-review`, or `travel`, and later choose one when generating a draft.

This is not model fine-tuning. Claude extracts reusable style guidance into local JSON, and later draft generation passes the selected profile as context.

## 2. Scope Decision

This cycle uses local sample files only.

Supported in this slice:

- `naver-bot profile-refresh [--profile <name>] <sample-file...>`
- `naver-bot draft [--profile <name>] <photo...> "메모"`
- Named style profile storage under `config/style_profiles/<profile-name>.json`
- `default` as the default profile name when `--profile` is omitted
- Offline unit tests using fake Claude completers

Out of scope for this slice:

- Direct Naver Blog scraping or Playwright-based post collection
- A Claude Code custom skill wrapper
- Profile listing, deletion, rename, merge, or search commands
- Migration from `config/style_profile.json`
- Storing raw sample post contents after profile extraction
- Few-shot example storage or retrieval

## 3. User Workflow

### Create or refresh the default profile

```bash
naver-bot profile-refresh samples/post1.md samples/post2.txt
```

This writes:

```text
config/style_profiles/default.json
```

### Create or refresh a category-specific profile

```bash
naver-bot profile-refresh --profile food-review samples/food1.md samples/food2.md
```

This writes:

```text
config/style_profiles/food-review.json
```

### Generate a draft with a selected profile

```bash
naver-bot draft --profile food-review photo1.jpg photo2.jpg "제품 첫인상이 좋고 사진은 두 장"
```

If `--profile` is omitted, draft generation uses `default`.

## 4. Profile Naming Rules

Profile names are used as local filenames, so the CLI must reject names that are not safe slugs.

Allowed profile names:

- lowercase ASCII letters
- digits
- hyphen (`-`)
- underscore (`_`)
- length 1-64
- no path separators
- no leading dot

Examples:

- valid: `default`, `food-review`, `product_review`, `travel2026`
- invalid: `../secret`, `.env`, `Food Review`, `맛집`, `food/review`, empty string

The first version should keep the validation strict and simple. Korean display labels can be added later if needed, but this slice only needs safe profile identifiers.

## 5. Data Model

The existing `StyleProfile` model remains the durable schema for writing style guidance.

Add one field:

```python
profile_name: str
```

Keep existing fields:

```python
blog_url: str
updated_at: datetime
structure_patterns: list[str]
tone_keywords: list[str]
frequent_expressions: list[str]
review_conventions: list[str]
photo_usage_notes: list[str]
```

`profile_name` stores the safe slug used for the filename. It is not a human display label.

## 6. Storage Design

Replace the single-profile path as the active write/read path:

```text
config/style_profile.json
```

with named profile paths:

```text
config/style_profiles/<profile-name>.json
```

`Settings` should expose:

```python
style_profiles_dir: Path
```

and the style profiler service should provide a single path builder for named profiles, such as:

```python
style_profile_path(settings: Settings, profile_name: str) -> Path
```

or an equivalent service-layer function that centralizes validation and path construction.

`ensure_local_directories()` must create `config/style_profiles/`.

The old `style_profile_path` property may be removed or left unused during implementation, but new profile reads and writes must use the named profile directory.

## 7. Claude Extraction Service

Add a style refresh service that accepts:

- `profile_name`
- `blog_url`
- local sample post texts
- a `TextCompleter` compatible with `ClaudeTextClient.complete_text()`

The service asks Claude to return JSON matching the `StyleProfile` schema. The prompt should instruct Claude to extract stable writing traits, not summarize the posts.

The service validates the response by parsing JSON and constructing `StyleProfile`. If Claude returns invalid JSON or a schema-invalid object, the service raises a clear error that the CLI can display.

The service should not access the filesystem directly except through explicit save/load helper calls. This keeps extraction testable with fake sample strings and fake Claude responses.

## 8. CLI Behavior

### `profile-refresh`

Inputs:

- `--profile <name>` option, defaulting to `default`
- one or more local sample file paths

Behavior:

1. Load settings.
2. Ensure local directories exist, including `config/style_profiles/`.
3. Validate profile name.
4. Validate at least one sample file path was provided.
5. Validate every sample path exists and is a file.
6. Read each sample as UTF-8 text.
7. Call the style refresh service with a `ClaudeTextClient`.
8. Save the validated profile to `config/style_profiles/<profile-name>.json`.
9. Print the saved path and number of sample files used.

Failure behavior:

- invalid profile name: print a short validation error and exit 1
- no sample files: print `Error: provide at least one sample post file` and exit 1
- missing sample file: print `Error: sample file not found: <path>` and exit 1
- invalid Claude profile response: print `Error: Claude returned an invalid style profile` and exit 1

### `draft`

Inputs:

- existing photo paths and memo behavior
- new `--profile <name>` option, defaulting to `default`

Behavior change:

- validate profile name
- load `config/style_profiles/<profile-name>.json`
- if missing, print `Style profile not found: <profile-name>. Run profile-refresh --profile <profile-name> first.` and exit 1
- pass the selected profile to `PostGenerator.generate()` as before

## 9. Tests

Unit tests should cover the feature without real Anthropic calls.

### Style profile path and validation

- valid names produce paths under `config/style_profiles/`
- invalid names are rejected
- path traversal attempts are rejected

### Refresh service

- fake completer returns valid JSON and produces a `StyleProfile`
- generated profile has the requested `profile_name`
- invalid JSON raises a clear error
- schema-invalid JSON raises a clear error

### CLI profile-refresh

- successful refresh writes `config/style_profiles/<name>.json`
- omitted `--profile` writes `default.json`
- invalid profile name exits 1
- missing sample file exits 1
- no sample files exits 1

### CLI draft profile selection

- omitted `--profile` loads `default.json`
- explicit `--profile food-review` loads `food-review.json`
- missing selected profile exits 1 with the profile-refresh hint
- invalid profile name exits 1

Existing draft tests should keep fake generator injection or monkeypatching so tests do not call Claude.

## 10. Documentation and Architecture Impact

Implementation will change the style profile storage path and draft data flow.

Required documentation updates during implementation:

- `docs/ai-context/architecture.md`
  - update module graph or data flow to mention `profile-refresh`
  - update draft flow from single `config/style_profile.json` to named `config/style_profiles/<profile>.json`
  - add an ADR for named local style profiles
- `docs/ai-context/domain-glossary.md`
  - update `스타일 프로필` mapping from single file to named profiles
  - add `프로필 이름` / `profile_name`
  - add `profile-refresh` / `profile_refresh_command`

No `docs/ai-context/non-obvious.md` update is needed unless implementation or closeout uncovers a tooling/process failure that passes the 5 Whys gate.

## 11. Future Claude Code Orchestrator Skill

After the CLI feature is stable, a separate custom skill can wrap the CLI into a guided conversation.

Possible skill flow:

1. Ask whether the user wants to create a new profile or use an existing one.
2. If creating a profile, ask for local sample post paths and run `naver-bot profile-refresh`.
3. Ask for photos and memo.
4. Run `naver-bot draft --profile <name>`.
5. Report the generated draft ID and preview command.

The skill should not contain core business logic. It should orchestrate the tested CLI commands and ask the missing-input questions in conversation.

This is intentionally out of scope for the current implementation cycle so the CLI remains the source of truth.

## 12. Self-Review

- Scope check: The spec implements local sample file profile refresh and draft profile selection only; Naver scraping and skill creation are deferred.
- Storage consistency: All new active reads and writes use `config/style_profiles/<profile-name>.json`; `default` is the default profile name.
- Safety check: Profile names are strict slugs to prevent path traversal and accidental writes outside the config directory.
- Testability check: Claude extraction is injectable through a fake completer, so unit tests remain offline.
- Architecture check: Named profiles affect settings, style profiler service, CLI draft flow, architecture docs, and glossary.
- Ambiguity check: The custom skill wrapper is explicitly future work, not part of this cycle.
