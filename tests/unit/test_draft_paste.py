from datetime import datetime, timezone
from pathlib import Path

from naver_blog_bot.post_generator.models import Draft


def _make_draft(body: str) -> Draft:
    return Draft(
        id="draft-20260606-120000",
        title="테스트 초안",
        memo="메모",
        body_markdown=body,
        photo_paths=[Path("photos/a.jpg")],
        created_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_paste_text_photo_marker_uses_basename_only() -> None:
    out = _make_draft("[사진: /home/indietogo/photos/IMG_1234.jpg]").to_paste_text()
    assert "[사진:" not in out
    assert "/home/" not in out
    assert "IMG_1234.jpg" in out
    assert "📷" in out


def test_paste_text_meme_marker_uses_label_when_present() -> None:
    out = _make_draft("[짤방: m1]").to_paste_text({"m1": "웃음, 만족"})
    assert "[짤방:" not in out
    assert "웃음, 만족" in out
    assert "🖼" in out  # part of 🖼️


def test_paste_text_meme_marker_falls_back_to_id_without_label() -> None:
    out = _make_draft("[짤방: satisfied]").to_paste_text()
    assert "[짤방:" not in out
    assert "satisfied" in out


def test_paste_text_emoticon_marker_preserves_type_inline() -> None:
    out = _make_draft("정말 좋았어요 {{이모티콘:만족}} 추천합니다").to_paste_text()
    assert "{{이모티콘:" not in out
    assert "만족" in out
    assert "😊" in out
    assert "정말 좋았어요" in out
    assert "추천합니다" in out


def test_paste_text_multiple_emoticons_on_one_line() -> None:
    out = _make_draft(
        "좋아요 {{이모티콘:기쁨}} 그리고 {{이모티콘:감탄}}"
    ).to_paste_text()
    assert "{{이모티콘:" not in out
    assert "기쁨" in out
    assert "감탄" in out


def test_paste_text_strips_heading_hashes() -> None:
    out = _make_draft("# 제목입니다\n\n## 소제목").to_paste_text()
    assert "제목입니다" in out
    assert "소제목" in out
    assert "#" not in out


def test_paste_text_preserves_plain_paragraph_and_blank_lines() -> None:
    out = _make_draft("첫 문단\n\n둘째 문단").to_paste_text()
    assert "첫 문단\n\n둘째 문단" in out


def test_paste_text_marker_free_text_has_no_cues() -> None:
    out = _make_draft("그냥 평범한 본문입니다.").to_paste_text()
    assert "〔" not in out
    assert "그냥 평범한 본문입니다." in out


def test_paste_text_full_body_no_raw_markers() -> None:
    body = (
        "# 체험단 후기\n\n"
        "[사진: /home/u/IMG_1.jpg]\n\n"
        "정말 좋았어요 {{이모티콘:만족}}\n\n"
        "[짤방: m1]"
    )
    out = _make_draft(body).to_paste_text({"m1": "웃음"})
    assert "[사진:" not in out
    assert "[짤방:" not in out
    assert "{{이모티콘:" not in out
    assert "/home/" not in out
