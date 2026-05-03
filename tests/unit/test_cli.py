from pathlib import Path

from typer.testing import CliRunner

from naver_blog_bot import cli
from naver_blog_bot.post_generator.drafts import DraftRepository
from naver_blog_bot.post_generator.models import Draft

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
    monkeypatch.setenv("NAVER_BOT_BROWSER_PROFILE_DIR", str(tmp_path / "browser-profile"))


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


def test_publish_command_is_blocked_in_foundation_slice(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)

    result = runner.invoke(cli.app, ["publish", "draft-20260503-120000"])

    assert result.exit_code == 1
    assert "publish is outside this foundation slice" in result.stdout
