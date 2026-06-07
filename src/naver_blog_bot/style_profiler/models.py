import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class StyleProfile(BaseModel):
    blog_url: str
    profile_name: str = "default"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    structure_patterns: list[str] = Field(default_factory=list)
    tone_keywords: list[str] = Field(default_factory=list)
    frequent_expressions: list[str] = Field(default_factory=list)
    review_conventions: list[str] = Field(default_factory=list)
    photo_usage_notes: list[str] = Field(default_factory=list)
    emoticon_usage_patterns: list[str] = Field(default_factory=list)
    meme_usage_patterns: list[str] = Field(default_factory=list)

    def to_cache_text(self) -> str:
        data = {
            "structure_patterns": self.structure_patterns,
            "tone_keywords": self.tone_keywords,
            "frequent_expressions": self.frequent_expressions,
            "review_conventions": self.review_conventions,
            "photo_usage_notes": self.photo_usage_notes,
            "emoticon_usage_patterns": self.emoticon_usage_patterns,
            "meme_usage_patterns": self.meme_usage_patterns,
        }
        return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
