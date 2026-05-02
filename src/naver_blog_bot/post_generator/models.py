from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class Draft(BaseModel):
    id: str
    title: str
    memo: str
    body_markdown: str
    photo_paths: list[Path]
    selected_memes: list[Path] = Field(default_factory=list)
    ogq_artwork_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def preview_text(self) -> str:
        photos = "\n".join(f"- {path}" for path in self.photo_paths) or "- (none)"
        memes = "\n".join(f"- {path}" for path in self.selected_memes) or "- (none)"
        ogq = self.ogq_artwork_id or "(none)"
        return (
            f"# {self.title}\n\n"
            f"Draft ID: {self.id}\n\n"
            f"Created: {self.created_at.isoformat()}\n\n"
            f"Memo: {self.memo}\n\n"
            f"Photos:\n{photos}\n\n"
            f"OGQ: {ogq}\n\n"
            f"Memes:\n{memes}\n\n"
            f"---\n\n"
            f"{self.body_markdown}\n"
        )
