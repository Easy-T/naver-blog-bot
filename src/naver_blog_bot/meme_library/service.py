from pathlib import Path

from naver_blog_bot.meme_library.models import MemeIndex
from naver_blog_bot.storage.json_store import read_json, write_json


def load_meme_index(path: Path) -> MemeIndex:
    if not path.exists():
        return MemeIndex()
    return MemeIndex.model_validate(read_json(path))


def save_meme_index(path: Path, index: MemeIndex) -> None:
    write_json(path, index.model_dump(mode="json"))
