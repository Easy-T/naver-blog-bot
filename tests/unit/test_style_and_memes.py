from datetime import datetime, timezone
from pathlib import Path

from naver_blog_bot.meme_library.models import MemeAsset, MemeIndex
from naver_blog_bot.meme_library.service import load_meme_index, save_meme_index
from naver_blog_bot.style_profiler.models import StyleProfile
from naver_blog_bot.style_profiler.service import (
    load_style_profile,
    save_style_profile,
    style_profile_path,
    validate_profile_name,
)


def test_missing_style_profile_returns_empty_profile(tmp_path: Path) -> None:
    profile = load_style_profile(
        tmp_path / "missing.json", "https://blog.naver.com/flowerbend"
    )

    assert profile.blog_url == "https://blog.naver.com/flowerbend"
    assert profile.structure_patterns == []
    assert profile.tone_keywords == []
    assert profile.emoticon_usage_patterns == []


def test_style_profile_round_trip(tmp_path: Path) -> None:
    profile = StyleProfile(
        blog_url="https://blog.naver.com/flowerbend",
        updated_at=datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc),
        structure_patterns=["도입부에 개인 경험을 먼저 말한다"],
        tone_keywords=["다정함", "솔직함"],
        frequent_expressions=["완전 만족"],
        review_conventions=["첫인상 다음에 사용 경험을 설명"],
        photo_usage_notes=["사진 사이에 짧은 감탄사를 넣음"],
        emoticon_usage_patterns=["단락 끝마다 이모티콘 1개"],
    )
    path = tmp_path / "style_profile.json"

    save_style_profile(path, profile)

    loaded = load_style_profile(path, profile.blog_url)
    assert loaded == profile
    assert "완전 만족" in profile.to_cache_text()
    assert "단락 끝마다 이모티콘 1개" in profile.to_cache_text()


def test_missing_meme_index_returns_empty_index(tmp_path: Path) -> None:
    index = load_meme_index(tmp_path / "missing.json")

    assert index.memes == []


def test_meme_index_round_trip_and_candidate_ranking(tmp_path: Path) -> None:
    index = MemeIndex(
        updated_at=datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc),
        memes=[
            MemeAsset(
                id="satisfied",
                path=Path("assets/memes/satisfied.png"),
                tags=["satisfaction", "food"],
                use_cases=["맛있었을 때", "만족"],
                alt_text="만족하는 표정",
            ),
            MemeAsset(
                id="surprise",
                path=Path("assets/memes/surprise.png"),
                tags=["surprise"],
                use_cases=["예상 밖"],
                alt_text="놀란 표정",
            ),
        ],
    )
    path = tmp_path / "meme_index.json"

    save_meme_index(path, index)
    loaded = load_meme_index(path)

    assert loaded == index
    assert (
        loaded.candidates_for_memo("음식이 맛있고 만족", limit=1)[0].id == "satisfied"
    )
    assert "satisfied.png" in loaded.to_cache_text()


def test_style_profile_default_profile_name() -> None:
    profile = StyleProfile(blog_url="https://blog.naver.com/flowerbend")
    assert profile.profile_name == "default"


def test_style_profile_explicit_profile_name() -> None:
    profile = StyleProfile(
        blog_url="https://blog.naver.com/flowerbend", profile_name="food-review"
    )
    assert profile.profile_name == "food-review"


def test_validate_profile_name_accepts_valid_names() -> None:
    for name in (
        "default",
        "food-review",
        "product_review",
        "travel2026",
        "a",
        "z" * 64,
    ):
        validate_profile_name(name)  # must not raise


def test_validate_profile_name_rejects_invalid_names() -> None:
    import pytest

    for name in (
        "",
        "Food Review",
        "맛집",
        "../secret",
        ".env",
        "food/review",
        "a" * 65,
    ):
        with pytest.raises(ValueError):
            validate_profile_name(name)


def test_style_profile_path_builds_correct_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAVER_BOT_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("NAVER_BOT_DRAFTS_DIR", str(tmp_path / "drafts"))
    monkeypatch.setenv("NAVER_BOT_MEMES_DIR", str(tmp_path / "assets" / "memes"))
    monkeypatch.setenv(
        "NAVER_BOT_BROWSER_PROFILE_DIR", str(tmp_path / "browser-profile")
    )
    from naver_blog_bot.config import Settings

    settings = Settings()
    path = style_profile_path(settings, "food-review")
    assert path == tmp_path / "config" / "style_profiles" / "food-review.json"


def test_style_profile_cache_text_excludes_volatile_fields() -> None:
    p1 = StyleProfile(
        blog_url="https://blog.naver.com/flowerbend",
        profile_name="default",
        structure_patterns=["도입부에 개인 경험"],
    )
    import time

    time.sleep(0.01)
    p2 = StyleProfile(
        blog_url="https://blog.naver.com/flowerbend",
        profile_name="default",
        structure_patterns=["도입부에 개인 경험"],
    )
    assert p1.to_cache_text() == p2.to_cache_text()
    assert "blog_url" not in p1.to_cache_text()
    assert "profile_name" not in p1.to_cache_text()
    assert "updated_at" not in p1.to_cache_text()


def test_meme_index_cache_text_excludes_updated_at() -> None:
    from datetime import datetime, timezone

    idx1 = MemeIndex(updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    idx2 = MemeIndex(updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert idx1.to_cache_text() == idx2.to_cache_text()
    assert "updated_at" not in idx1.to_cache_text()


def test_style_profile_path_rejects_invalid_name(monkeypatch, tmp_path: Path) -> None:
    import pytest

    monkeypatch.setenv("NAVER_BOT_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("NAVER_BOT_DRAFTS_DIR", str(tmp_path / "drafts"))
    monkeypatch.setenv("NAVER_BOT_MEMES_DIR", str(tmp_path / "assets" / "memes"))
    monkeypatch.setenv(
        "NAVER_BOT_BROWSER_PROFILE_DIR", str(tmp_path / "browser-profile")
    )
    from naver_blog_bot.config import Settings

    settings = Settings()
    with pytest.raises(ValueError):
        style_profile_path(settings, "../secret")


def test_tag_meme_image_parses_vision_response(tmp_path: Path) -> None:
    from naver_blog_bot.meme_library.service import tag_meme_image

    image_path = tmp_path / "happy.jpg"
    image_path.write_bytes(b"fake image")

    class FakeVisionClient:
        def complete_vision(self, *, image_path, prompt):
            return '{"tags": ["기쁨", "만족"], "use_cases": ["후기 마무리", "만족 표현"], "alt_text": "기쁜 표정"}'

    asset = tag_meme_image(image_path, FakeVisionClient())
    assert asset.id == "happy"
    assert asset.path == image_path
    assert "기쁨" in asset.tags
    assert "후기 마무리" in asset.use_cases
    assert asset.alt_text == "기쁜 표정"


def test_tag_meme_image_handles_invalid_json(tmp_path: Path) -> None:
    import pytest
    from naver_blog_bot.meme_library.service import tag_meme_image

    image_path = tmp_path / "bad.jpg"
    image_path.write_bytes(b"fake")

    class BrokenVision:
        def complete_vision(self, *, image_path, prompt):
            return "이건 JSON이 아님"

    with pytest.raises(ValueError, match="Vision"):
        tag_meme_image(image_path, BrokenVision())


def test_ensure_in_memes_dir_copies_outside_file(tmp_path: Path) -> None:
    from naver_blog_bot.meme_library.service import ensure_in_memes_dir

    memes = tmp_path / "memes"
    src = tmp_path / "src" / "happy.png"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"img")

    dest = ensure_in_memes_dir(src, memes)
    assert dest == memes / "happy.png"
    assert dest.read_bytes() == b"img"
    assert src.exists()


def test_ensure_in_memes_dir_keeps_file_already_inside(tmp_path: Path) -> None:
    from naver_blog_bot.meme_library.service import ensure_in_memes_dir

    memes = tmp_path / "memes"
    memes.mkdir()
    f = memes / "inside.png"
    f.write_bytes(b"x")

    dest = ensure_in_memes_dir(f, memes)
    assert dest == f


def test_ensure_in_memes_dir_suffixes_on_name_clash(tmp_path: Path) -> None:
    from naver_blog_bot.meme_library.service import ensure_in_memes_dir

    memes = tmp_path / "memes"
    memes.mkdir()
    (memes / "dup.png").write_bytes(b"existing")
    src = tmp_path / "dup.png"
    src.write_bytes(b"new")

    dest = ensure_in_memes_dir(src, memes)
    assert dest == memes / "dup-2.png"
    assert dest.read_bytes() == b"new"


def test_extract_meme_json_handles_code_fence() -> None:
    from naver_blog_bot.meme_library.service import _extract_meme_json

    raw = '```json\n{"tags": ["기쁨"], "use_cases": ["마무리"], "alt_text": "웃음"}\n```'
    data = _extract_meme_json(raw)
    assert data["tags"] == ["기쁨"]


def test_extract_meme_json_handles_surrounding_prose() -> None:
    from naver_blog_bot.meme_library.service import _extract_meme_json

    raw = (
        "다음은 메타데이터입니다:\n"
        '{"tags": ["놀람"], "use_cases": ["반전"], "alt_text": "놀란 표정"}\n'
        "참고하세요."
    )
    data = _extract_meme_json(raw)
    assert data["tags"] == ["놀람"]


def test_extract_meme_json_raises_on_garbage() -> None:
    import pytest

    from naver_blog_bot.meme_library.service import _extract_meme_json

    with pytest.raises(ValueError, match="invalid JSON"):
        _extract_meme_json("이건 JSON이 전혀 아님")
