from pathlib import Path

from typer.testing import CliRunner

from naver_blog_bot import cli
from naver_blog_bot.blog_scraper.models import (
    EmoticonBlock,
    ImageBlock,
    PostDocument,
    TextBlock,
)
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
    from naver_blog_bot.style_profiler.service import (
        save_style_profile,
        style_profile_path,
    )

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


def test_draft_reports_claude_backend_errors(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake image bytes")

    from naver_blog_bot.config import Settings, ensure_local_directories
    from naver_blog_bot.shared.claude_client import ClaudeBackendError
    from naver_blog_bot.style_profiler.models import StyleProfile
    from naver_blog_bot.style_profiler.service import (
        save_style_profile,
        style_profile_path,
    )

    settings = Settings()
    ensure_local_directories(settings)
    save_style_profile(
        style_profile_path(settings, "default"),
        StyleProfile(blog_url=settings.blog_url),
    )

    class BrokenGenerator:
        def generate(self, **kwargs):
            raise ClaudeBackendError("Claude Code CLI failed. Run `claude` once.")

    monkeypatch.setattr(cli, "build_generator", lambda settings: BrokenGenerator())

    result = runner.invoke(cli.app, ["draft", str(photo), "메모"])

    assert result.exit_code == 1
    assert "Claude Code CLI failed" in result.stdout


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
    assert "Preview opened:" in result.stdout
    assert "draft-20260503-120000.html" in result.stdout


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


def test_profile_refresh_reports_claude_backend_errors(
    monkeypatch, tmp_path: Path
) -> None:
    configure_paths(monkeypatch, tmp_path)
    sample = tmp_path / "sample.txt"
    sample.write_text("샘플 본문", encoding="utf-8")

    from naver_blog_bot.shared.claude_client import ClaudeBackendError

    def broken_refresh(**kwargs):
        raise ClaudeBackendError("Claude Code CLI failed. Run `claude` once.")

    monkeypatch.setattr(cli, "refresh_style_profile", broken_refresh)

    result = runner.invoke(cli.app, ["profile-refresh", str(sample)])

    assert result.exit_code == 1
    assert "Claude Code CLI failed" in result.stdout


def test_profile_refresh_with_explicit_profile_name(
    monkeypatch, tmp_path: Path
) -> None:
    configure_paths(monkeypatch, tmp_path)
    sample = tmp_path / "post.md"
    sample.write_text("샘플", encoding="utf-8")
    monkeypatch.setattr(cli, "refresh_style_profile", FakeRefreshService())

    result = runner.invoke(
        cli.app, ["profile-refresh", "--profile", "food-review", str(sample)]
    )

    assert result.exit_code == 0
    assert "food-review.json" in result.stdout
    assert (tmp_path / "config" / "style_profiles" / "food-review.json").exists()


def test_profile_refresh_rejects_invalid_profile_name(
    monkeypatch, tmp_path: Path
) -> None:
    configure_paths(monkeypatch, tmp_path)

    result = runner.invoke(
        cli.app, ["profile-refresh", "--profile", "Invalid Name", "any.md"]
    )

    assert result.exit_code == 1
    assert "Invalid profile name" in result.stdout


def test_profile_refresh_rejects_missing_sample_file(
    monkeypatch, tmp_path: Path
) -> None:
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
    from naver_blog_bot.style_profiler.service import (
        save_style_profile,
        style_profile_path,
    )

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
    from naver_blog_bot.style_profiler.service import (
        save_style_profile,
        style_profile_path,
    )

    settings = Settings()
    ensure_local_directories(settings)
    save_style_profile(
        style_profile_path(settings, "food-review"),
        StyleProfile(blog_url=settings.blog_url, profile_name="food-review"),
    )

    result = runner.invoke(
        cli.app, ["draft", "--profile", "food-review", str(photo), "메모"]
    )

    assert result.exit_code == 0
    assert "Draft saved" in result.stdout


def test_draft_exits_when_named_profile_missing(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake image bytes")
    monkeypatch.setattr(cli, "build_generator", lambda settings: FakeGenerator())

    result = runner.invoke(
        cli.app, ["draft", "--profile", "food-review", str(photo), "메모"]
    )

    assert result.exit_code == 1
    assert "profile-refresh --profile food-review" in result.stdout


def test_draft_rejects_invalid_profile_name(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake image bytes")

    result = runner.invoke(
        cli.app, ["draft", "--profile", "Invalid!", str(photo), "메모"]
    )

    assert result.exit_code == 1
    assert "Invalid profile name" in result.stdout


def _make_fake_document(title: str, text: str) -> PostDocument:
    return PostDocument(
        url="https://m.blog.naver.com/user/123",
        title=title,
        blocks=[
            TextBlock(content=text),
            ImageBlock(alt="사진"),
            EmoticonBlock(description="기쁨"),
        ],
    )


class FakeScrapeService:
    def __init__(self, documents: list[PostDocument]) -> None:
        self._documents = documents
        self.calls: list[tuple[str, int, object]] = []

    def __call__(self, url: str, count: int, settings: object) -> list[PostDocument]:
        self.calls.append((url, count, settings))
        return self._documents


def test_profile_refresh_url_source(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    doc = _make_fake_document("맛집 리뷰", "정말 맛있었어요")
    fake_scrape = FakeScrapeService([doc])
    monkeypatch.setattr(cli, "scrape_source", fake_scrape)
    monkeypatch.setattr(cli, "refresh_style_profile", FakeRefreshService())

    result = runner.invoke(
        cli.app,
        ["profile-refresh", "--count", "2", "https://m.blog.naver.com/user/123"],
    )

    assert result.exit_code == 0, result.stdout
    assert len(fake_scrape.calls) == 1
    called_url, called_count, _ = fake_scrape.calls[0]
    assert called_url == "https://m.blog.naver.com/user/123"
    assert called_count == 2
    assert "1 sample(s) used" in result.stdout

    profile_file = tmp_path / "config" / "style_profiles" / "default.json"
    assert profile_file.exists()


def test_profile_refresh_rejects_non_positive_count(
    monkeypatch, tmp_path: Path
) -> None:
    configure_paths(monkeypatch, tmp_path)

    result = runner.invoke(
        cli.app,
        ["profile-refresh", "--count", "0", "https://m.blog.naver.com/user/123"],
    )

    assert result.exit_code == 1
    assert "count must be at least 1" in result.stdout


def test_profile_refresh_empty_url_result_exits_1(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    fake_scrape = FakeScrapeService([])
    monkeypatch.setattr(cli, "scrape_source", fake_scrape)

    result = runner.invoke(
        cli.app,
        ["profile-refresh", "https://m.blog.naver.com/user/123"],
    )

    assert result.exit_code == 1
    assert "Error: no posts found at https://m.blog.naver.com/user/123" in result.stdout


def test_profile_refresh_url_source_structured_text_passed_to_refresh(
    monkeypatch, tmp_path: Path
) -> None:
    configure_paths(monkeypatch, tmp_path)
    doc = _make_fake_document("제목입니다", "본문 텍스트")
    fake_scrape = FakeScrapeService([doc])
    monkeypatch.setattr(cli, "scrape_source", fake_scrape)

    received_sample_texts: list[list[str]] = []
    received_blog_urls: list[str] = []

    def capturing_refresh(*, profile_name, blog_url, sample_texts, completer):
        received_sample_texts.append(list(sample_texts))
        received_blog_urls.append(blog_url)
        return StyleProfile(profile_name=profile_name, blog_url=blog_url)

    monkeypatch.setattr(cli, "refresh_style_profile", capturing_refresh)

    result = runner.invoke(
        cli.app,
        ["profile-refresh", "https://m.blog.naver.com/user/123"],
    )

    assert result.exit_code == 0, result.stdout
    assert len(received_sample_texts) == 1
    assert received_blog_urls == ["https://m.blog.naver.com/user/123"]
    texts = received_sample_texts[0]
    assert len(texts) == 1
    structured = texts[0]
    assert "제목입니다" in structured
    assert "본문 텍스트" in structured
    assert "[이미지]" in structured
    assert "[이모티콘:기쁨]" in structured


def test_profile_refresh_mixed_local_and_url(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    local_file = tmp_path / "local.md"
    local_file.write_text("로컬 샘플 내용", encoding="utf-8")

    doc = _make_fake_document("URL 포스트", "URL 본문")
    fake_scrape = FakeScrapeService([doc])
    monkeypatch.setattr(cli, "scrape_source", fake_scrape)

    received_sample_texts: list[list[str]] = []

    def capturing_refresh(*, profile_name, blog_url, sample_texts, completer):
        received_sample_texts.append(list(sample_texts))
        return StyleProfile(profile_name=profile_name, blog_url=blog_url)

    monkeypatch.setattr(cli, "refresh_style_profile", capturing_refresh)

    result = runner.invoke(
        cli.app,
        ["profile-refresh", str(local_file), "https://m.blog.naver.com/user/123"],
    )

    assert result.exit_code == 0, result.stdout
    texts = received_sample_texts[0]
    assert len(texts) == 2
    assert "로컬 샘플 내용" in texts[0]
    assert "URL 포스트" in texts[1]
    assert "2 sample(s) used" in result.stdout


def test_profile_refresh_url_before_local(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    local_file = tmp_path / "local.md"
    local_file.write_text("로컬 샘플 내용", encoding="utf-8")

    doc = _make_fake_document("URL 포스트", "URL 본문")
    fake_scrape = FakeScrapeService([doc])
    monkeypatch.setattr(cli, "scrape_source", fake_scrape)

    received_sample_texts: list[list[str]] = []

    def capturing_refresh(*, profile_name, blog_url, sample_texts, completer):
        received_sample_texts.append(list(sample_texts))
        return StyleProfile(profile_name=profile_name, blog_url=blog_url)

    monkeypatch.setattr(cli, "refresh_style_profile", capturing_refresh)

    result = runner.invoke(
        cli.app,
        ["profile-refresh", "https://m.blog.naver.com/user/123", str(local_file)],
    )

    assert result.exit_code == 0, result.stdout
    texts = received_sample_texts[0]
    assert len(texts) == 2
    assert "URL 포스트" in texts[0]
    assert "로컬 샘플 내용" in texts[1]
    assert "2 sample(s) used" in result.stdout


def test_profile_refresh_scraper_value_error_exits_1(
    monkeypatch, tmp_path: Path
) -> None:
    configure_paths(monkeypatch, tmp_path)

    def failing_scrape(url: str, count: int, settings: object) -> list[PostDocument]:
        raise ValueError("unsupported URL scheme")

    monkeypatch.setattr(cli, "scrape_source", failing_scrape)

    result = runner.invoke(
        cli.app,
        ["profile-refresh", "https://m.blog.naver.com/user/123"],
    )

    assert result.exit_code == 1
    assert "Error: unsupported URL scheme" in result.stdout


def test_profile_refresh_missing_local_file_still_errors(
    monkeypatch, tmp_path: Path
) -> None:
    configure_paths(monkeypatch, tmp_path)

    result = runner.invoke(
        cli.app,
        ["profile-refresh", str(tmp_path / "nonexistent.md")],
    )

    assert result.exit_code == 1
    assert "sample file not found" in result.stdout
