import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from naver_blog_bot.config import Settings
from naver_blog_bot.shared.claude_client import (
    ClaudeBackendError,
    ClaudeCodeTextClient,
    ClaudeTextClient,
    build_text_completer,
)


class FakeMessages:
    def __init__(self) -> None:
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="생성된 본문")]
        )


class FakeAnthropic:
    def __init__(self) -> None:
        self.messages = FakeMessages()


def test_complete_text_uses_configured_model_and_cache_blocks() -> None:
    fake = FakeAnthropic()
    settings = Settings(claude_model="claude-opus-4-7", claude_max_tokens=1234)
    client = ClaudeTextClient(settings=settings, anthropic_client=fake)

    text = client.complete_text(
        system_prompt="너는 블로그 글쓰기 도우미다.",
        cacheable_context=["style profile", "meme index"],
        user_prompt="메모로 초안을 작성해줘.",
    )

    assert text == "생성된 본문"
    assert fake.messages.last_kwargs["model"] == "claude-opus-4-7"
    assert fake.messages.last_kwargs["max_tokens"] == 1234
    assert fake.messages.last_kwargs["thinking"] == {"type": "adaptive"}
    assert fake.messages.last_kwargs["messages"] == [
        {"role": "user", "content": "메모로 초안을 작성해줘."}
    ]
    assert fake.messages.last_kwargs["system"] == [
        {"type": "text", "text": "너는 블로그 글쓰기 도우미다."},
        {
            "type": "text",
            "text": "style profile",
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": "meme index", "cache_control": {"type": "ephemeral"}},
    ]


def test_complete_text_accepts_dict_text_blocks_from_fake_clients() -> None:
    class DictMessages:
        def create(self, **kwargs):
            return SimpleNamespace(content=[{"type": "text", "text": "딕셔너리 본문"}])

    fake = SimpleNamespace(messages=DictMessages())
    client = ClaudeTextClient(settings=Settings(), anthropic_client=fake)

    assert (
        client.complete_text(system_prompt="system", user_prompt="user")
        == "딕셔너리 본문"
    )


def test_claude_code_client_calls_claude_print_json(monkeypatch) -> None:
    calls = []

    def fake_run(args, *, input, capture_output, text, check, timeout):
        calls.append(
            {
                "args": args,
                "input": input,
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
            "input": "# System instructions\n\n시스템 지시\n\n# Context 1\n\n문체\n\n# Context 2\n\n짤방\n\n# User request\n\n초안을 써줘",
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


def test_build_text_completer_auto_uses_sdk_when_claude_command_missing(
    monkeypatch,
) -> None:
    fake = FakeAnthropic()
    monkeypatch.setattr("shutil.which", lambda command: None)

    client = build_text_completer(
        Settings(claude_backend="auto"), anthropic_client=fake
    )

    assert isinstance(client, ClaudeTextClient)


def test_claude_code_vision_client_builds_correct_args(monkeypatch) -> None:
    calls = []
    inputs = []

    def fake_run(args, *, input, capture_output, text, check, timeout):
        calls.append(args)
        inputs.append(input)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(
                {
                    "type": "result",
                    "result": '{"tags": ["만족"], "use_cases": ["후기 마무리"], "alt_text": "만족 표정"}',
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = ClaudeCodeTextClient(settings=Settings())
    result = client.complete_vision(
        image_path=Path("/tmp/test.jpg"),
        prompt="이 이미지를 분석해라",
    )

    assert (
        result
        == '{"tags": ["만족"], "use_cases": ["후기 마무리"], "alt_text": "만족 표정"}'
    )
    # cycle 9: Claude Code CLI has no --image option; the image path is embedded
    # in the prompt (sent via stdin), so it appears in the input, not in argv.
    assert "--image" not in calls[0]
    assert "/tmp/test.jpg" in inputs[0]


def test_claude_code_vision_raises_on_failure(monkeypatch) -> None:
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=1, stdout="", stderr="image not found"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = ClaudeCodeTextClient(settings=Settings())

    with pytest.raises(ClaudeBackendError) as exc:
        client.complete_vision(image_path=Path("/tmp/x.jpg"), prompt="분석해라")

    assert "Claude Code CLI failed" in str(exc.value)
