from pathlib import Path

from naver_blog_bot.meme_harvester.service import _parse_classification, classify_image


def test_parse_classification_reads_is_meme_and_fields() -> None:
    raw = (
        '{"is_meme": true, "tags": ["놀람"], '
        '"use_cases": ["반전 강조"], "alt_text": "놀란 강아지"}'
    )
    data = _parse_classification(raw)
    assert data["is_meme"] is True
    assert data["tags"] == ["놀람"]
    assert data["use_cases"] == ["반전 강조"]
    assert data["alt_text"] == "놀란 강아지"


def test_parse_classification_defaults_when_garbage() -> None:
    data = _parse_classification("not json")
    assert data["is_meme"] is False
    assert data["tags"] == []


def test_classify_image_passes_context_into_prompt(tmp_path: Path) -> None:
    img = tmp_path / "m.jpg"
    img.write_bytes(b"x")
    seen = {}

    class FakeVision:
        def complete_vision(self, *, image_path, prompt):
            seen["prompt"] = prompt
            return '{"is_meme": true, "tags": ["웃음"], "use_cases": ["유머"], "alt_text": "ㅋㅋ"}'

    data = classify_image(img, FakeVision(), context="너무 웃겨서 빵 터졌어요")
    assert data["is_meme"] is True
    assert "너무 웃겨서 빵 터졌어요" in seen["prompt"]
