import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from naver_blog_bot.config import Settings


class ClaudeBackendError(RuntimeError):
    pass


class ClaudeTextClient:
    def __init__(self, settings: Settings, anthropic_client: Any | None = None) -> None:
        self.settings = settings
        self.client = anthropic_client or Anthropic()

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        cacheable_context: Sequence[str] = (),
    ) -> str:
        system_blocks: list[dict[str, Any]] = [{"type": "text", "text": system_prompt}]
        for context in cacheable_context:
            system_blocks.append(
                {
                    "type": "text",
                    "text": context,
                    "cache_control": {"type": "ephemeral"},
                }
            )

        message = self.client.messages.create(
            model=self.settings.claude_model,
            max_tokens=self.settings.claude_max_tokens,
            thinking={"type": "adaptive"},
            system=system_blocks,
            messages=[{"role": "user", "content": user_prompt}],
        )

        parts: list[str] = []
        for block in message.content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block["text"]))
            elif getattr(block, "type", None) == "text":
                parts.append(str(block.text))
        return "".join(parts).strip()

    def complete_vision(self, *, image_path: Path, prompt: str) -> str:
        import base64

        image_data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")
        suffix = image_path.suffix.lower().lstrip(".")
        media_type_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }
        media_type = media_type_map.get(suffix, "image/jpeg")

        message = self.client.messages.create(
            model=self.settings.claude_model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        parts: list[str] = []
        for block in message.content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block["text"]))
            elif getattr(block, "type", None) == "text":
                parts.append(str(block.text))
        return "".join(parts).strip()


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
                "Claude Code CLI returned non-JSON output despite --output-format json."
            ) from exc

        if isinstance(payload, dict) and isinstance(payload.get("result"), str):
            return payload["result"].strip()

        raise ClaudeBackendError(
            "Claude Code CLI JSON output did not include result text."
        )

    def complete_vision(self, *, image_path: Path, prompt: str) -> str:
        abs_path = Path(image_path).resolve()
        full_prompt = f"{prompt}\n\n분석할 이미지 파일 경로: {abs_path}"
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
                input=full_prompt,
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
                f"Claude Code CLI timed out after {self.settings.claude_cli_timeout_seconds}s."
            ) from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise ClaudeBackendError(f"Claude Code CLI failed. Detail: {detail}")

        return self._parse_output(result.stdout)


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
