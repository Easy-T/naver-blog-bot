import re
from pathlib import Path

from naver_blog_bot.config import Settings
from naver_blog_bot.storage.json_store import read_json, write_json
from naver_blog_bot.style_profiler.models import StyleProfile

_SLUG_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


def validate_profile_name(name: str) -> None:
    if not _SLUG_RE.match(name):
        raise ValueError(
            f"Invalid profile name: {name!r}. "
            "Use only lowercase letters, digits, hyphens, and underscores (1-64 chars)."
        )


def style_profile_path(settings: Settings, profile_name: str) -> Path:
    validate_profile_name(profile_name)
    return settings.style_profiles_dir / f"{profile_name}.json"


def load_style_profile(path: Path, blog_url: str) -> StyleProfile:
    if not path.exists():
        return StyleProfile(blog_url=blog_url)
    return StyleProfile.model_validate(read_json(path))


def save_style_profile(path: Path, profile: StyleProfile) -> None:
    write_json(path, profile.model_dump(mode="json"))
