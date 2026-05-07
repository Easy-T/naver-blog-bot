from pathlib import Path

from typer.testing import CliRunner

from naver_blog_bot import cli
from naver_blog_bot.post_generator.drafts import DraftRepository
from naver_blog_bot.post_generator.models import Draft
from naver_blog_bot.style_profiler.models import StyleProfile

runner = CliRunner()


class FakeGenerator:
    def generate(self, *, photo_paths, memo, style_profile, meme_index):
        return Draft(
            id="draft-20260503-120000",
            title="포포몬 체험단 후기",
            memo=memo,
            body_markdown="# 포포몬 체험단 후기\n\n본문입니다.",
            photo_paths=photo_paths,
            selected_memes=[],
            ogq_artwork_id="644e042a7d7f8",
        )


def configure_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAVER_BOT_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("NAVER_BOT_DRAFTS_DIR", str(tmp_path / "drafts"))
    monkeypatch.setenv("NAVER_BOT_MEMES_DIR", str(tmp_path / "assets" / "memes"))
    monkeypatch.setenv(
        "NAVER_BOT_BROWSER_PROFILE_DIR", str(tmp_path / "browser-profile")
    )


def test_init_creates_local_directories(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)

    result = runner.invoke(cli.app, ["init"])

    assert result.exit_code == 0
    assert "Local project state is ready" in result.stdout
    assert (tmp_path / "config").is_dir()
    assert (tmp_path / "drafts").is_dir()
    assert (tmp_path / "assets" / "memes").is_dir()
    assert (tmp_path / "browser-profile").is_dir()


def test_draft_saves_generated_draft(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake image bytes")
    monkeypatch.setattr(cli, "build_generator", lambda settings: FakeGenerator())

    from naver_blog_bot.config import Settings, ensure_local_directories
    from naver_blog_bot.style_profiler.models import StyleProfile
    from naver_blog_bot.style_profiler.service import save_style_profile, style_profile_path
    settings = Settings()
    ensure_local_directories(settings)
    save_style_profile(
        style_profile_path(settings, "default"),
        StyleProfile(blog_url=settings.blog_url),
    )

    result = runner.invoke(cli.app, ["draft", str(photo), "제품이 만족스러웠음"])

    assert result.exit_code == 0
    assert "Draft saved: draft-20260503-120000" in result.stdout
    loaded = DraftRepository(tmp_path / "drafts").load("draft-20260503-120000")
    assert loaded.memo == "제품이 만족스러웠음"
    assert loaded.photo_paths == [photo]


def test_draft_requires_photo_and_memo(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)

    result = runner.invoke(cli.app, ["draft", "메모만 있음"])

    assert result.exit_code != 0
    assert "provide at least one photo path and a memo" in result.stdout


def test_draft_rejects_missing_photo(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)

    result = runner.invoke(cli.app, ["draft", str(tmp_path / "missing.jpg"), "메모"])

    assert result.exit_code != 0
    assert "photo not found" in result.stdout


def test_preview_outputs_saved_draft(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    repo = DraftRepository(tmp_path / "drafts")
    repo.save(
        Draft(
            id="draft-20260503-120000",
            title="포포몬 체험단 후기",
            memo="미리보기 메모",
            body_markdown="# 포포몬 체험단 후기\n\n본문입니다.",
            photo_paths=[Path("photo.jpg")],
            ogq_artwork_id="644e042a7d7f8",
        )
    )

    result = runner.invoke(cli.app, ["preview", "draft-20260503-120000"])

    assert result.exit_code == 0
    assert "Draft ID: draft-20260503-120000" in result.stdout
    assert "미리보기 메모" in result.stdout


def test_publish_command_is_blocked_in_foundation_slice(
    monkeypatch, tmp_path: Path
) -> None:
    configure_paths(monkeypatch, tmp_path)

    result = runner.invoke(cli.app, ["publish", "draft-20260503-120000"])

    assert result.exit_code == 1
    assert "publish is outside this foundation slice" in result.stdout


class FakeRefreshService:
    def __call__(self, *, profile_name, blog_url, sample_texts, completer):
        return StyleProfile(
            profile_name=profile_name,
            blog_url=blog_url,
            tone_keywords=["테스트"],
        )


def test_profile_refresh_writes_named_profile(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    sample = tmp_path / "post.md"
    sample.write_text("샘플 포스트 내용", encoding="utf-8")
    monkeypatch.setattr(cli, "refresh_style_profile", FakeRefreshService())

    result = runner.invoke(cli.app, ["profile-refresh", str(sample)])

    assert result.exit_code == 0
    assert "default.json" in result.stdout
    profile_file = tmp_path / "config" / "style_profiles" / "default.json"
    assert profile_file.exists()


def test_profile_refresh_with_explicit_profile_name(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    sample = tmp_path / "post.md"
    sample.write_text("샘플", encoding="utf-8")
    monkeypatch.setattr(cli, "refresh_style_profile", FakeRefreshService())

    result = runner.invoke(cli.app, ["profile-refresh", "--profile", "food-review", str(sample)])

    assert result.exit_code == 0
    assert "food-review.json" in result.stdout
    assert (tmp_path / "config" / "style_profiles" / "food-review.json").exists()


def test_profile_refresh_rejects_invalid_profile_name(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)

    result = runner.invoke(cli.app, ["profile-refresh", "--profile", "Invalid Name", "any.md"])

    assert result.exit_code == 1
    assert "Invalid profile name" in result.stdout


def test_profile_refresh_rejects_missing_sample_file(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)

    result = runner.invoke(cli.app, ["profile-refresh", str(tmp_path / "missing.md")])

    assert result.exit_code == 1
    assert "sample file not found" in result.stdout


def test_profile_refresh_rejects_no_sample_files(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)

    result = runner.invoke(cli.app, ["profile-refresh"])

    assert result.exit_code != 0


def test_draft_uses_default_profile_when_omitted(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake image bytes")
    monkeypatch.setattr(cli, "build_generator", lambda settings: FakeGenerator())

    from naver_blog_bot.config import Settings, ensure_local_directories
    from naver_blog_bot.style_profiler.models import StyleProfile
    from naver_blog_bot.style_profiler.service import save_style_profile, style_profile_path
    settings = Settings()
    ensure_local_directories(settings)
    save_style_profile(
        style_profile_path(settings, "default"),
        StyleProfile(blog_url=settings.blog_url, profile_name="default"),
    )

    result = runner.invoke(cli.app, ["draft", str(photo), "메모"])

    assert result.exit_code == 0
    assert "Draft saved" in result.stdout


def test_draft_loads_explicit_named_profile(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake image bytes")
    monkeypatch.setattr(cli, "build_generator", lambda settings: FakeGenerator())

    from naver_blog_bot.config import Settings, ensure_local_directories
    from naver_blog_bot.style_profiler.models import StyleProfile
    from naver_blog_bot.style_profiler.service import save_style_profile, style_profile_path
    settings = Settings()
    ensure_local_directories(settings)
    save_style_profile(
        style_profile_path(settings, "food-review"),
        StyleProfile(blog_url=settings.blog_url, profile_name="food-review"),
    )

    result = runner.invoke(cli.app, ["draft", "--profile", "food-review", str(photo), "메모"])

    assert result.exit_code == 0
    assert "Draft saved" in result.stdout


def test_draft_exits_when_named_profile_missing(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake image bytes")
    monkeypatch.setattr(cli, "build_generator", lambda settings: FakeGenerator())

    result = runner.invoke(cli.app, ["draft", "--profile", "food-review", str(photo), "메모"])

    assert result.exit_code == 1
    assert "profile-refresh --profile food-review" in result.stdout


def test_draft_rejects_invalid_profile_name(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake image bytes")

    result = runner.invoke(cli.app, ["draft", "--profile", "Invalid!", str(photo), "메모"])

    assert result.exit_code == 1
    assert "Invalid profile name" in result.stdout
