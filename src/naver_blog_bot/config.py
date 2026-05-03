from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NAVER_BOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    blog_url: str = "https://blog.naver.com/flowerbend"
    ogq_artwork_id: str = "644e042a7d7f8"
    ogq_name: str = "세루리안"
    config_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "config")
    drafts_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "drafts")
    memes_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "assets" / "memes")
    browser_profile_dir: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "browser-profile"
    )
    claude_model: str = "claude-opus-4-7"
    claude_max_tokens: int = 4000

    @property
    def style_profile_path(self) -> Path:
        return self.config_dir / "style_profile.json"

    @property
    def meme_index_path(self) -> Path:
        return self.config_dir / "meme_index.json"


def get_settings() -> Settings:
    return Settings()


def ensure_local_directories(settings: Settings) -> list[Path]:
    paths = [
        settings.config_dir,
        settings.drafts_dir,
        settings.memes_dir,
        settings.browser_profile_dir,
    ]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    return paths
