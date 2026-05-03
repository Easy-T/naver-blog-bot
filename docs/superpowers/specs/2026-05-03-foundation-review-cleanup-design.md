# Foundation Review Cleanup Design

Created: 2026-05-03
Project: naver-blog-bot

## 1. Goal

Clean up the small issues found during the Foundation slice reviews without changing product behavior or expanding the foundation scope.

This cleanup keeps the repository's guidance and type hints aligned with the code that now exists after the Foundation slice.

## 2. Scope

Update only the review-noted items:

1. Refresh the project `CLAUDE.md` module list so it no longer says there are no modules.
2. Add the missing direct `cli.py -> shared/claude_client.py` edge to the live architecture graph.
3. Reword the architecture data-flow step for `naver-bot draft` so it reflects the actual order: load settings, ensure local directories, then validate photo paths.
4. Add missing parameter type annotations to `PostGenerator._build_user_prompt()`.
5. Align `TextCompleter.cacheable_context` with `ClaudeTextClient.complete_text()` by using `Sequence[str]` consistently.

## 3. Out of Scope

This cleanup must not add new commands, change CLI behavior, alter prompt text, change JSON formats, modify draft IDs, add type-checker tooling, or implement any deferred Phase 1 features such as scraping, Playwright publishing, CAPTCHA/session handling, EXIF stripping, OGQ UI insertion, meme vision tagging, or Telegram support.

## 4. Design

### Documentation updates

`CLAUDE.md` should list the live modules introduced by the Foundation slice:

- `config.py`
- `storage/json_store.py`
- `style_profiler`
- `meme_library`
- `post_generator`
- `shared/claude_client.py`
- `cli.py`

`docs/ai-context/architecture.md` should keep its existing module graph but add the direct dependency from `cli.py` to `shared/claude_client.py`, because `build_generator()` imports and constructs `ClaudeTextClient` directly.

The same file should reword data-flow step 2 to say that `cli.py` loads `Settings`, ensures local directories exist, and validates photo paths.

### Code updates

`src/naver_blog_bot/post_generator/generator.py` should import `Sequence` from `collections.abc` and `MemeAsset` from `naver_blog_bot.meme_library.models`.

`TextCompleter.complete_text()` should accept `cacheable_context: Sequence[str]`, matching `ClaudeTextClient.complete_text()`.

`PostGenerator._build_user_prompt()` should annotate:

- `photo_paths: list[Path]`
- `memo: str`
- `selected_memes: list[MemeAsset]`

No runtime logic should change.

## 5. Verification

Run the full existing suite:

```bash
uv run pytest -v
```

Expected result: all 22 tests pass.

Run the CLI help smoke check:

```bash
uv run naver-bot --help
```

Expected result: exit 0 and the implemented commands remain listed.

Check git status before committing to ensure only the intended cleanup files changed.

## 6. Risks

- `CLAUDE.md` changes affect prompt cache stability, so this cleanup should be done once and kept small.
- Mermaid graph edits can drift from actual imports; the new edge is limited to a direct import already present in `cli.py`.
- Type annotation changes should avoid behavior changes and should be verified by the existing tests.

## 7. Self-Review

- Scope check: focused on five review-noted cleanup items only.
- Safety check: no external-state automation or publishing behavior is added.
- Placeholder check: no placeholder requirements remain.
- Ambiguity check: each file-level change has a concrete target and verification path.
