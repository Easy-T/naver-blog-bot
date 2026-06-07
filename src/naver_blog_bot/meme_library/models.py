import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class MemeAsset(BaseModel):
    id: str
    path: Path
    tags: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    alt_text: str = ""
    frequency: int = 1


class MemeIndex(BaseModel):
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    memes: list[MemeAsset] = Field(default_factory=list)

    def candidates_for_memo(self, memo: str, limit: int = 3) -> list[MemeAsset]:
        normalized = memo.lower()
        scored: list[tuple[int, MemeAsset]] = []
        for meme in self.memes:
            score = sum(1 for tag in meme.tags if tag.lower() in normalized)
            score += sum(
                1 for use_case in meme.use_cases if use_case.lower() in normalized
            )
            if score > 0:
                scored.append((score, meme))
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return [meme for _, meme in scored[:limit]]

    def top_by_frequency(self, limit: int = 3) -> list["MemeAsset"]:
        ranked = sorted(self.memes, key=lambda m: (-m.frequency, m.id))
        return ranked[:limit]

    def to_cache_text(self) -> str:
        data = {"memes": [m.model_dump(mode="json") for m in self.memes]}
        return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
