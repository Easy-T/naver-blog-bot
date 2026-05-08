**Status:** completed
**RPI-Cycle:** 5
**Started:** 2026-05-09

# Claude Code Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let local users generate drafts and refresh style profiles without a separate Anthropic API key by optionally routing Claude calls through the authenticated Claude Code CLI.

**Architecture:** Preserve the existing `TextCompleter` boundary and add backend selection in the shared Claude client layer. `auto` mode prefers `claude -p --output-format json` when the executable is available, then falls back to the existing Anthropic SDK path; explicit modes fail with actionable setup messages.

**Tech Stack:** Python 3.11+, Typer, pydantic-settings, Anthropic Python SDK, Claude Code CLI subprocess, pytest, ruff.

---

## User Convenience and Functional Re-review

### Convenience risks checked

- API key setup should no longer be required for the default local happy path.
- The user should not need to change existing `naver-bot profile-refresh`, `naver-bot draft`, or `naver-bot preview` command syntax.
- Failure messages must tell the user which backend failed and what to run next, e.g. install/login to Claude Code or set `NAVER_BOT_CLAUDE_BACKEND=anthropic-sdk` with `ANTHROPIC_API_KEY`.
- Existing API-key users must still be able to force the SDK path.

### Functional risks checked

- Claude Code credentials are not reused directly. The app only launches the documented `claude` CLI subprocess.
- Do not use `--bare`, because it skips OAuth/keychain reads and defeats the user's Claude Code-login goal.
- Prompt caching remains available only on the SDK backend; Claude Code backend sends one complete prompt through the CLI.
- `claude_model` can be passed to the CLI with `--model`, but `claude_max_tokens` remains SDK-only unless Claude Code CLI later exposes an equivalent stable flag.
- `profile-refresh` expects JSON from Claude, so subprocess JSON parsing must extract the CLI response text, not the CLI metadata object.
- `auto` prefers Claude Code CLI when installed. Users with both CLI and API key can force SDK with `NAVER_BOT_CLAUDE_BACKEND=anthropic-sdk`.

---

## File Structure

- Modify `src/naver_blog_bot/config.py`
  - Add backend settings: `claude_backend`, `claude_command`, `claude_cli_timeout_seconds`.
- Modify `src/naver_blog_bot/shared/claude_client.py`
  - Keep `ClaudeTextClient` for Anthropic SDK.
  - Add `ClaudeCodeTextClient` for subprocess execution.
  - Add `build_text_completer(settings)` factory.
  - Add focused exception type for setup/runtime guidance.
- Modify `src/naver_blog_bot/cli.py`
  - Replace direct `ClaudeTextClient(...)` construction with `build_text_completer(settings)`.
  - Catch backend errors in generation commands and print user-friendly messages.
- Modify `tests/unit/test_config.py`
  - Cover new setting defaults and environment overrides.
- Modify `tests/unit/test_claude_client.py`
  - Cover backend factory, subprocess command shape, JSON parsing, and failure guidance.
- Modify `tests/unit/test_cli.py`
  - Cover CLI error display when backend setup/runtime fails.
- Modify `README.md`
  - Reframe API key as optional SDK backend credential.
  - Add Claude Code login/setup path.
- Modify `docs/ai-context/architecture.md`
  - Append ADR for selectable Claude backend and update data-flow references if implementation changes the module graph wording.
- Modify `docs/ai-context/runbook.md`
  - Add local troubleshooting commands for Claude Code backend.

---

### Task 1: Add backend settings

**Files:**
- Modify: `src/naver_blog_bot/config.py`
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: Write failing config tests**

Add these tests to `tests/unit/test_config.py`:

```python
def test_settings_defaults_to_auto_claude_backend() -> None:
    settings = Settings()

    assert settings.claude_backend == "auto"
    assert settings.claude_command == "claude"
    assert settings.claude_cli_timeout_seconds == 300


def test_settings_accepts_claude_backend_overrides(monkeypatch) -> None:
    monkeypatch.setenv("NAVER_BOT_CLAUDE_BACKEND", "claude-code")
    monkeypatch.setenv("NAVER_BOT_CLAUDE_COMMAND", "custom-claude")
    monkeypatch.setenv("NAVER_BOT_CLAUDE_CLI_TIMEOUT_SECONDS", "120")

    settings = Settings()

    assert settings.claude_backend == "claude-code"
    assert settings.claude_command == "custom-claude"
    assert settings.claude_cli_timeout_seconds == 120
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/unit/test_config.py::test_settings_defaults_to_auto_claude_backend tests/unit/test_config.py::test_settings_accepts_claude_backend_overrides -v
```

Expected: FAIL because `Settings` has no new backend fields.

- [ ] **Step 3: Implement settings**

Change `src/naver_blog_bot/config.py` to import `Literal` and add fields:

```python
from pathlib import Path
from typing import Literal
```

Inside `Settings` after `claude_max_tokens`:

```python
    claude_backend: Literal["auto", "claude-code", "anthropic-sdk"] = "auto"
    claude_command: str = "claude"
    claude_cli_timeout_seconds: int = 300
```

- [ ] **Step 4: Run config tests**

Run:

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: PASS.

---

### Task 2: Add Claude Code subprocess completer

**Files:**
- Modify: `src/naver_blog_bot/shared/claude_client.py`
- Test: `tests/unit/test_claude_client.py`

- [ ] **Step 1: Write failing subprocess tests**

Add these tests to `tests/unit/test_claude_client.py`:

```python
import json
import subprocess


def test_claude_code_client_calls_claude_print_json(monkeypatch) -> None:
    calls = []

    def fake_run(args, *, capture_output, text, check, timeout):
        calls.append(
            {
                "args": args,
                "capture_output": capture_output,
                "text": text,
                "check": check,
                "timeout": timeout,
            }
        )
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps({"type": "result", "result": "CLI 본문"}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = ClaudeCodeTextClient(settings=Settings(claude_cli_timeout_seconds=120))

    text = client.complete_text(
        system_prompt="시스템 지시",
        cacheable_context=["문체", "짤방"],
        user_prompt="초안을 써줘",
    )

    assert text == "CLI 본문"
    assert calls == [
        {
            "args": [
                "claude",
                "-p",
                "--output-format",
                "json",
                "--model",
                "claude-opus-4-7",
            ],
            "capture_output": True,
            "text": True,
            "check": False,
            "timeout": 120,
        }
    ]


def test_claude_code_client_sends_combined_prompt_on_stdin(monkeypatch) -> None:
    captured = {}

    def fake_run(args, *, input, capture_output, text, check, timeout):
        captured["input"] = input
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps({"type": "result", "result": "완료"}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = ClaudeCodeTextClient(settings=Settings())

    client.complete_text(
        system_prompt="시스템 지시",
        cacheable_context=["문체", "짤방"],
        user_prompt="초안을 써줘",
    )

    assert "시스템 지시" in captured["input"]
    assert "문체" in captured["input"]
    assert "짤방" in captured["input"]
    assert "초안을 써줘" in captured["input"]


def test_claude_code_client_reports_login_or_runtime_failure(monkeypatch) -> None:
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="",
            stderr="not logged in",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = ClaudeCodeTextClient(settings=Settings())

    with pytest.raises(ClaudeBackendError) as excinfo:
        client.complete_text(system_prompt="system", user_prompt="user")

    assert "Claude Code CLI failed" in str(excinfo.value)
    assert "not logged in" in str(excinfo.value)
```

Also add missing imports at the top of the test file:

```python
import pytest

from naver_blog_bot.shared.claude_client import (
    ClaudeBackendError,
    ClaudeCodeTextClient,
    ClaudeTextClient,
)
```

Keep the existing `ClaudeTextClient` import behavior by replacing the old single-class import with this grouped import.

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/unit/test_claude_client.py -v
```

Expected: FAIL because `ClaudeCodeTextClient` and `ClaudeBackendError` do not exist.

- [ ] **Step 3: Implement subprocess completer**

Update `src/naver_blog_bot/shared/claude_client.py` with these additions while keeping existing `ClaudeTextClient` behavior:

```python
import json
import subprocess
from collections.abc import Sequence
from typing import Any
```

Add below imports/classes:

```python
class ClaudeBackendError(RuntimeError):
    pass
```

Add this class after `ClaudeTextClient`:

```python
class ClaudeCodeTextClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        cacheable_context: Sequence[str] = (),
    ) -> str:
        prompt = self._build_prompt(
            system_prompt=system_prompt,
            cacheable_context=cacheable_context,
            user_prompt=user_prompt,
        )
        args = [
            self.settings.claude_command,
            "-p",
            "--output-format",
            "json",
            "--model",
            self.settings.claude_model,
        ]
        try:
            result = subprocess.run(
                args,
                input=prompt,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.settings.claude_cli_timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise ClaudeBackendError(
                "Claude Code CLI not found. Install Claude Code or set "
                "NAVER_BOT_CLAUDE_BACKEND=anthropic-sdk with ANTHROPIC_API_KEY."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ClaudeBackendError(
                f"Claude Code CLI timed out after "
                f"{self.settings.claude_cli_timeout_seconds} seconds."
            ) from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise ClaudeBackendError(
                "Claude Code CLI failed. Run `claude` once to confirm login, "
                "or set NAVER_BOT_CLAUDE_BACKEND=anthropic-sdk with "
                f"ANTHROPIC_API_KEY. Detail: {detail}"
            )

        return self._parse_output(result.stdout)

    def _build_prompt(
        self,
        *,
        system_prompt: str,
        cacheable_context: Sequence[str],
        user_prompt: str,
    ) -> str:
        parts = [
            "# System instructions",
            system_prompt,
        ]
        for index, context in enumerate(cacheable_context, start=1):
            parts.extend([f"# Context {index}", context])
        parts.extend(["# User request", user_prompt])
        return "\n\n".join(parts)

    def _parse_output(self, stdout: str) -> str:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ClaudeBackendError(
                "Claude Code CLI returned non-JSON output despite "
                "--output-format json."
            ) from exc

        if isinstance(payload, dict) and isinstance(payload.get("result"), str):
            return payload["result"].strip()

        raise ClaudeBackendError("Claude Code CLI JSON output did not include result text.")
```

- [ ] **Step 4: Run Claude client tests**

Run:

```bash
uv run pytest tests/unit/test_claude_client.py -v
```

Expected: PASS.

---

### Task 3: Add backend factory and CLI wiring

**Files:**
- Modify: `src/naver_blog_bot/shared/claude_client.py`
- Modify: `src/naver_blog_bot/cli.py`
- Test: `tests/unit/test_claude_client.py`
- Test: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing factory tests**

Add to `tests/unit/test_claude_client.py`:

```python
def test_build_text_completer_uses_explicit_claude_code_backend() -> None:
    client = build_text_completer(Settings(claude_backend="claude-code"))

    assert isinstance(client, ClaudeCodeTextClient)


def test_build_text_completer_uses_explicit_sdk_backend() -> None:
    fake = FakeAnthropic()

    client = build_text_completer(
        Settings(claude_backend="anthropic-sdk"), anthropic_client=fake
    )

    assert isinstance(client, ClaudeTextClient)


def test_build_text_completer_auto_prefers_claude_command(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda command: "/usr/bin/claude")

    client = build_text_completer(Settings(claude_backend="auto"))

    assert isinstance(client, ClaudeCodeTextClient)


def test_build_text_completer_auto_uses_sdk_when_claude_command_missing(monkeypatch) -> None:
    fake = FakeAnthropic()
    monkeypatch.setattr("shutil.which", lambda command: None)

    client = build_text_completer(Settings(claude_backend="auto"), anthropic_client=fake)

    assert isinstance(client, ClaudeTextClient)
```

Add `build_text_completer` to the grouped import.

- [ ] **Step 2: Run failing factory tests**

Run:

```bash
uv run pytest tests/unit/test_claude_client.py -v
```

Expected: FAIL because `build_text_completer` does not exist.

- [ ] **Step 3: Implement factory**

In `src/naver_blog_bot/shared/claude_client.py`, add import:

```python
import shutil
```

Add at the bottom:

```python
def build_text_completer(
    settings: Settings, anthropic_client: Any | None = None
) -> ClaudeTextClient | ClaudeCodeTextClient:
    if settings.claude_backend == "claude-code":
        return ClaudeCodeTextClient(settings=settings)
    if settings.claude_backend == "anthropic-sdk":
        return ClaudeTextClient(settings=settings, anthropic_client=anthropic_client)
    if shutil.which(settings.claude_command):
        return ClaudeCodeTextClient(settings=settings)
    return ClaudeTextClient(settings=settings, anthropic_client=anthropic_client)
```

- [ ] **Step 4: Wire CLI to factory**

Change import in `src/naver_blog_bot/cli.py`:

```python
from naver_blog_bot.shared.claude_client import ClaudeBackendError, build_text_completer
```

Change `build_generator`:

```python
def build_generator(settings: Settings) -> PostGenerator:
    return PostGenerator(settings=settings, claude_client=build_text_completer(settings))
```

Change `profile_refresh_command` completer argument:

```python
            completer=build_text_completer(settings),
```

Wrap both `refresh_style_profile(...)` and `build_generator(settings).generate(...)` call sites with `except ClaudeBackendError as exc` that prints `Error: {exc}` and exits 1.

For `profile_refresh_command`, use:

```python
    try:
        result = refresh_style_profile(
            profile_name=profile,
            blog_url=blog_url,
            sample_texts=sample_texts,
            completer=build_text_completer(settings),
        )
    except ClaudeBackendError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)
    except ValueError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)
```

For `draft_command`, use:

```python
    try:
        draft = build_generator(settings).generate(
            photo_paths=photo_paths,
            memo=memo,
            style_profile=style_profile,
            meme_index=meme_index,
        )
    except ClaudeBackendError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)
```

- [ ] **Step 5: Write CLI backend error tests**

Add to `tests/unit/test_cli.py`:

```python
def test_draft_reports_claude_backend_errors(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake image bytes")

    from naver_blog_bot.config import Settings, ensure_local_directories
    from naver_blog_bot.shared.claude_client import ClaudeBackendError
    from naver_blog_bot.style_profiler.models import StyleProfile
    from naver_blog_bot.style_profiler.service import save_style_profile, style_profile_path

    settings = Settings()
    ensure_local_directories(settings)
    save_style_profile(style_profile_path(settings, "default"), StyleProfile(blog_url=settings.blog_url))

    class BrokenGenerator:
        def generate(self, **kwargs):
            raise ClaudeBackendError("Claude Code CLI failed. Run `claude` once.")

    monkeypatch.setattr(cli, "build_generator", lambda settings: BrokenGenerator())

    result = runner.invoke(cli.app, ["draft", str(photo), "메모"])

    assert result.exit_code == 1
    assert "Claude Code CLI failed" in result.stdout


def test_profile_refresh_reports_claude_backend_errors(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    sample = tmp_path / "sample.txt"
    sample.write_text("샘플 본문", encoding="utf-8")

    from naver_blog_bot.shared.claude_client import ClaudeBackendError

    def broken_refresh(**kwargs):
        raise ClaudeBackendError("Claude Code CLI failed. Run `claude` once.")

    monkeypatch.setattr(cli, "refresh_style_profile", broken_refresh)

    result = runner.invoke(cli.app, ["profile-refresh", str(sample)])

    assert result.exit_code == 1
    assert "Claude Code CLI failed" in result.stdout
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest tests/unit/test_claude_client.py tests/unit/test_cli.py -v
```

Expected: PASS.

---

### Task 4: Update docs and architecture records

**Files:**
- Modify: `README.md`
- Modify: `docs/ai-context/architecture.md`
- Modify: `docs/ai-context/runbook.md`

- [ ] **Step 1: Update README setup wording**

In `README.md`, change prerequisites from Anthropic API key as required to Claude Code CLI login as recommended and API key as optional fallback.

Replace the `.env` example with:

```bash
# .env

# 기본값: auto
# - auto: Claude Code CLI가 있으면 사용, 없으면 Anthropic SDK 사용
# - claude-code: Claude Code CLI만 사용
# - anthropic-sdk: Anthropic SDK만 사용
NAVER_BOT_CLAUDE_BACKEND=auto

# Claude Code CLI 명령 이름. 보통 변경하지 않아도 됩니다.
NAVER_BOT_CLAUDE_COMMAND=claude

# Anthropic SDK 백엔드를 강제로 쓸 때만 필요합니다.
# ANTHROPIC_API_KEY=sk-ant-...

# 내 블로그 주소 (profile-refresh의 기본 blog_url로 사용됨)
NAVER_BOT_BLOG_URL=https://blog.naver.com/내아이디

# OGQ 이모티콘 (사용하는 이모티콘 세트 정보, 없으면 생략 가능)
NAVER_BOT_OGQ_ARTWORK_ID=644e042a7d7f8
NAVER_BOT_OGQ_NAME=세루리안
```

Add a short Claude Code setup section before `.env`:

```markdown
### 0단계 — Claude Code 로그인 확인

API 키 없이 쓰려면 PC에 Claude Code CLI가 설치되어 있고 로그인되어 있어야 합니다.

```bash
claude
```

위 명령으로 Claude Code가 정상 실행되는지 확인하세요. `naver-bot`은 내부적으로 `claude -p --output-format json`을 호출합니다.
```

- [ ] **Step 2: Update settings table**

In README settings table, add:

```markdown
| `NAVER_BOT_CLAUDE_BACKEND` | `auto` | Claude 호출 방식 (`auto`, `claude-code`, `anthropic-sdk`) |
| `NAVER_BOT_CLAUDE_COMMAND` | `claude` | Claude Code CLI 실행 명령 |
| `NAVER_BOT_CLAUDE_CLI_TIMEOUT_SECONDS` | `300` | Claude Code CLI 응답 대기 시간(초) |
```

Change `ANTHROPIC_API_KEY` row to optional SDK-only wording.

- [ ] **Step 3: Append ADR**

Append to `docs/ai-context/architecture.md` under ADRs:

```markdown
### ADR-004: Claude calls support selectable local backends

- 날짜: 2026-05-09
- 상태: Accepted
- 결정: Claude text completion is selected through `build_text_completer()`, with `auto`, `claude-code`, and `anthropic-sdk` backends. The default `auto` mode prefers the installed Claude Code CLI and falls back to the existing Anthropic SDK path when the CLI command is unavailable.
- 이유: The tool is local-first and the target user already runs Claude Code locally, so requiring a separate API key is unnecessary friction for the common path.
- 대안: Remove SDK support entirely; keep API-key-only generation; export prompts for manual copy/paste into Claude Code.
- 트레이드오프: Claude Code backend cannot use SDK prompt-cache block semantics and depends on local CLI availability/login state, but it removes API key setup for local users while keeping SDK fallback for automation.
```

Update data-flow step 6 wording from direct SDK call to selectable text completer.

- [ ] **Step 4: Update runbook troubleshooting**

Add to `docs/ai-context/runbook.md` Common Operations:

```markdown
### Check Claude backend

```bash
claude
```

If `naver-bot draft` reports a Claude Code CLI error:
- Run `claude` once and confirm it is installed and logged in.
- Force Claude Code mode with `NAVER_BOT_CLAUDE_BACKEND=claude-code` when testing local login behavior.
- Force SDK mode with `NAVER_BOT_CLAUDE_BACKEND=anthropic-sdk` and set `ANTHROPIC_API_KEY` when using API-key automation.
```

- [ ] **Step 5: Run documentation grep checks**

Run:

```bash
uv run pytest tests/unit/test_config.py tests/unit/test_claude_client.py tests/unit/test_cli.py -v
```

Expected: PASS.

Also inspect README occurrences of `ANTHROPIC_API_KEY` and confirm none call it globally required.

---

### Task 5: Full verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run project quality gate**

Run:

```bash
bash scripts/check.sh
```

Expected: exit code 0.

- [ ] **Step 2: Smoke-test backend selection without calling real Claude**

Run:

```bash
uv run pytest tests/unit/test_claude_client.py::test_build_text_completer_auto_prefers_claude_command tests/unit/test_claude_client.py::test_build_text_completer_auto_uses_sdk_when_claude_command_missing -v
```

Expected: PASS.

- [ ] **Step 3: Review diff for scope**

Run:

```bash
git diff -- README.md docs/ai-context/architecture.md docs/ai-context/runbook.md src/naver_blog_bot/config.py src/naver_blog_bot/shared/claude_client.py src/naver_blog_bot/cli.py tests/unit/test_config.py tests/unit/test_claude_client.py tests/unit/test_cli.py
```

Expected: diff only contains backend selection, subprocess completer, docs, and tests described in this plan.

- [ ] **Step 4: Do not commit unless explicitly requested**

This repository's execution policy requires explicit user approval before creating git commits.

---

## Self-Review

- Spec coverage: Covers user convenience review, API-key reduction, Claude Code CLI subprocess path, SDK preservation, tests, README, runbook, and ADR.
- Placeholder scan: No TBD/TODO/fill-later steps remain.
- Type consistency: `ClaudeBackendError`, `ClaudeCodeTextClient`, `ClaudeTextClient`, and `build_text_completer(settings, anthropic_client=None)` are consistently named across tasks.
- Scope check: No publishing, prompt-export mode, new storage, or UI behavior is included.
