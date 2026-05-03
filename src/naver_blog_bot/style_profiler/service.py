from pathlib import Path

from naver_blog_bot.storage.json_store import read_json, write_json
from naver_blog_bot.style_profiler.models import StyleProfile


def load_style_profile(path: Path, blog_url: str) -> StyleProfile:
    if not path.exists():
        return StyleProfile(blog_url=blog_url)
    return StyleProfile.model_validate(read_json(path))


def save_style_profile(path: Path, profile: StyleProfile) -> None:
    write_json(path, profile.model_dump(mode="json"))
