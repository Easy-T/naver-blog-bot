from datetime import datetime, timezone
from pathlib import Path

from naver_blog_bot.post_generator.models import Draft


def _make_draft(body: str) -> Draft:
    return Draft(
        id="draft-20260529-120000",
        title="테스트 초안",
        memo="테스트 메모",
        body_markdown=body,
        photo_paths=[Path("photos/a.jpg")],
        created_at=datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_to_html_contains_title() -> None:
    draft = _make_draft("# 제목\n\n본문입니다.")
    html = draft.to_html()
    assert "테스트 초안" in html
    assert "<h1>" in html


def test_to_html_renders_photo_placeholder() -> None:
    draft = _make_draft("[사진: photos/a.jpg]")
    html = draft.to_html()
    assert "photo-placeholder" in html
    assert "photos/a.jpg" in html


def test_to_html_renders_emoticon_badge() -> None:
    draft = _make_draft("재미있었어요. {{이모티콘:기쁨}}")
    html = draft.to_html()
    assert "emoticon-badge" in html
    assert "기쁨" in html


def test_to_html_renders_meme_placeholder() -> None:
    draft = _make_draft("[짤방: satisfied]")
    html = draft.to_html()
    assert "meme-placeholder" in html
    assert "satisfied" in html


def test_to_html_escapes_html_special_chars() -> None:
    draft = _make_draft("A < B & C > D")
    html = draft.to_html()
    assert "&lt;" in html
    assert "&amp;" in html
    assert "&gt;" in html


def test_to_html_is_valid_html_structure() -> None:
    draft = _make_draft("본문")
    html = draft.to_html()
    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="ko">' in html
    assert "</html>" in html
