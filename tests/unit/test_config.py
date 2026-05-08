from pathlib import Path

from naver_blog_bot.config import Settings, ensure_local_directories


def test_settings_defaults_point_to_project_local_paths() -> None:
    settings = Settings()

    assert settings.blog_url == "https://blog.naver.com/flowerbend"
    assert settings.ogq_artwork_id == "644e042a7d7f8"
    assert settings.ogq_name == "세루리안"
    assert settings.config_dir.name == "config"
    assert settings.drafts_dir.name == "drafts"
    assert settings.memes_dir.parts[-2:] == ("assets", "memes")
    assert settings.browser_profile_dir.name == "browser-profile"
    assert settings.style_profile_path == settings.config_dir / "style_profile.json"
    assert settings.meme_index_path == settings.config_dir / "meme_index.json"
    assert settings.claude_model == "claude-opus-4-7"
    assert settings.claude_max_tokens == 4000


def test_settings_accept_environment_path_overrides(
    monkeypatch, tmp_path: Path
) -> None:
    drafts_dir = tmp_path / "draft-output"
    monkeypatch.setenv("NAVER_BOT_DRAFTS_DIR", str(drafts_dir))

    settings = Settings()

    assert settings.drafts_dir == drafts_dir


def test_ensure_local_directories_creates_expected_paths(tmp_path: Path) -> None:
    settings = Settings(
        config_dir=tmp_path / "config",
        drafts_dir=tmp_path / "drafts",
        memes_dir=tmp_path / "assets" / "memes",
        browser_profile_dir=tmp_path / "browser-profile",
    )

    created = ensure_local_directories(settings)

    assert created == [
        settings.config_dir,
        settings.style_profiles_dir,
        settings.drafts_dir,
        settings.memes_dir,
        settings.browser_profile_dir,
    ]
    for path in created:
        assert path.is_dir()


def test_settings_has_style_profiles_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAVER_BOT_CONFIG_DIR", str(tmp_path / "config"))
    from naver_blog_bot.config import Settings

    settings = Settings()
    assert settings.style_profiles_dir == tmp_path / "config" / "style_profiles"


def test_ensure_local_directories_creates_style_profiles_dir(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("NAVER_BOT_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("NAVER_BOT_DRAFTS_DIR", str(tmp_path / "drafts"))
    monkeypatch.setenv("NAVER_BOT_MEMES_DIR", str(tmp_path / "assets" / "memes"))
    monkeypatch.setenv(
        "NAVER_BOT_BROWSER_PROFILE_DIR", str(tmp_path / "browser-profile")
    )
    from naver_blog_bot.config import Settings, ensure_local_directories

    settings = Settings()
    ensure_local_directories(settings)
    assert (tmp_path / "config" / "style_profiles").is_dir()
