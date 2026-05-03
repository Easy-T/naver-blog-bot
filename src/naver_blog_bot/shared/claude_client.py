from collections.abc import Sequence
from typing import Any

from anthropic import Anthropic

from naver_blog_bot.config import Settings


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
