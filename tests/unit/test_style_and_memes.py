from datetime import datetime, timezone
from pathlib import Path

from naver_blog_bot.meme_library.models import MemeAsset, MemeIndex
from naver_blog_bot.meme_library.service import load_meme_index, save_meme_index
from naver_blog_bot.style_profiler.models import StyleProfile
from naver_blog_bot.style_profiler.service import load_style_profile, save_style_profile


def test_missing_style_profile_returns_empty_profile(tmp_path: Path) -> None:
    profile = load_style_profile(
        tmp_path / "missing.json", "https://blog.naver.com/flowerbend"
    )

    assert profile.blog_url == "https://blog.naver.com/flowerbend"
    assert profile.structure_patterns == []
    assert profile.tone_keywords == []


def test_style_profile_round_trip(tmp_path: Path) -> None:
    profile = StyleProfile(
        blog_url="https://blog.naver.com/flowerbend",
        updated_at=datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc),
        structure_patterns=["도입부에 개인 경험을 먼저 말한다"],
        tone_keywords=["다정함", "솔직함"],
        frequent_expressions=["완전 만족"],
        review_conventions=["첫인상 다음에 사용 경험을 설명"],
        photo_usage_notes=["사진 사이에 짧은 감탄사를 넣음"],
    )
    path = tmp_path / "style_profile.json"

    save_style_profile(path, profile)

    assert load_style_profile(path, profile.blog_url) == profile
    assert "완전 만족" in profile.to_cache_text()


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
