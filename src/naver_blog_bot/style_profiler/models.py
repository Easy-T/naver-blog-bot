import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class StyleProfile(BaseModel):
    blog_url: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    structure_patterns: list[str] = Field(default_factory=list)
    tone_keywords: list[str] = Field(default_factory=list)
    frequent_expressions: list[str] = Field(default_factory=list)
    review_conventions: list[str] = Field(default_factory=list)
    photo_usage_notes: list[str] = Field(default_factory=list)

    def to_cache_text(self) -> str:
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
