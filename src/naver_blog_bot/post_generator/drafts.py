from datetime import datetime
from pathlib import Path

from naver_blog_bot.post_generator.models import Draft
from naver_blog_bot.storage.json_store import read_json, write_json


def draft_id_from_time(now: datetime) -> str:
    return now.strftime("draft-%Y%m%d-%H%M%S")


class DraftRepository:
    def __init__(self, drafts_dir: Path) -> None:
        self.drafts_dir = drafts_dir

    def path_for(self, draft_id: str) -> Path:
        return self.drafts_dir / f"{draft_id}.json"

    def save(self, draft: Draft) -> Path:
        path = self.path_for(draft.id)
        write_json(path, draft.model_dump(mode="json"))
        return path

    def load(self, draft_id: str) -> Draft:
        return Draft.model_validate(read_json(self.path_for(draft_id)))
