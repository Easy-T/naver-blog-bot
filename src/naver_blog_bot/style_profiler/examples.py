from pathlib import Path

from pydantic import BaseModel

from naver_blog_bot.storage.json_store import read_json, write_json

_MAX_EXAMPLES = 3


class ExamplePost(BaseModel):
    title: str
    url: str
    structured_text: str


class FewShotRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, examples: list[ExamplePost]) -> None:
        kept = examples[:_MAX_EXAMPLES]
        write_json(self.path, [e.model_dump() for e in kept])

    def load(self) -> list[ExamplePost]:
        if not self.path.exists():
            return []
        return [ExamplePost(**item) for item in read_json(self.path)]

    def exists(self) -> bool:
        return self.path.exists()
