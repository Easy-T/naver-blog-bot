from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


class TextCompleter(Protocol):
    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        cacheable_context: Sequence[str] = (),
    ) -> str: ...


class VisionCompleter(Protocol):
    def complete_vision(self, *, image_path: Path, prompt: str) -> str: ...
