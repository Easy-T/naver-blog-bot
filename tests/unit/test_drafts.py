from datetime import datetime, timezone
from pathlib import Path

from naver_blog_bot.post_generator.drafts import DraftRepository, draft_id_from_time
from naver_blog_bot.post_generator.models import Draft


def test_draft_id_from_time_is_stable() -> None:
    now = datetime(2026, 5, 3, 12, 34, 56, tzinfo=timezone.utc)

    assert draft_id_from_time(now) == "draft-20260503-123456"


def test_draft_repository_saves_and_loads_json(tmp_path: Path) -> None:
    created_at = datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc)
    draft = Draft(
        id="draft-20260503-120000",
        title="포포몬 체험단 후기",
        memo="사진은 다섯 장이고 첫인상이 좋았음",
        body_markdown="# 포포몬 체험단 후기\n\n본문입니다.",
        photo_paths=[Path("photos/one.jpg"), Path("photos/two.jpg")],
        selected_memes=[Path("assets/memes/smile.png")],
        ogq_artwork_id="644e042a7d7f8",
        created_at=created_at,
    )
    repo = DraftRepository(tmp_path)

    saved_path = repo.save(draft)
    loaded = repo.load("draft-20260503-120000")

    assert saved_path == tmp_path / "draft-20260503-120000.json"
    assert loaded == draft


def test_draft_preview_text_is_readable() -> None:
    draft = Draft(
        id="draft-20260503-120000",
        title="포포몬 체험단 후기",
        memo="첫인상이 좋았음",
        body_markdown="# 포포몬 체험단 후기\n\n본문입니다.",
        photo_paths=[Path("photos/one.jpg")],
        selected_memes=[],
        ogq_artwork_id="644e042a7d7f8",
        created_at=datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc),
    )

    preview = draft.preview_text()

    assert "Draft ID: draft-20260503-120000" in preview
    assert "Memo: 첫인상이 좋았음" in preview
    assert "photos/one.jpg" in preview
    assert "OGQ: 644e042a7d7f8" in preview
    assert "# 포포몬 체험단 후기" in preview
