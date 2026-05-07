import json
import pytest
from collections.abc import Sequence

from naver_blog_bot.style_profiler.models import StyleProfile
from naver_blog_bot.style_profiler.refresh import refresh_style_profile


class FakeCompleter:
    def __init__(self, response: str) -> None:
        self._response = response

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        cacheable_context: Sequence[str] = (),
    ) -> str:
        return self._response


VALID_RESPONSE = json.dumps(
    {
        "structure_patterns": ["도입부에 개인 경험을 먼저 쓴다"],
        "tone_keywords": ["다정함", "솔직함"],
        "frequent_expressions": ["완전 만족"],
        "review_conventions": ["첫인상 후 사용 경험 순"],
        "photo_usage_notes": ["사진 아래 짧은 감탄사"],
    }
)


def test_refresh_returns_style_profile_with_profile_name() -> None:
    completer = FakeCompleter(VALID_RESPONSE)
    profile = refresh_style_profile(
        profile_name="food-review",
        blog_url="https://blog.naver.com/flowerbend",
        sample_texts=["샘플 포스트 텍스트"],
        completer=completer,
    )
    assert isinstance(profile, StyleProfile)
    assert profile.profile_name == "food-review"
    assert profile.blog_url == "https://blog.naver.com/flowerbend"
    assert "다정함" in profile.tone_keywords


def test_refresh_sets_all_fields() -> None:
    completer = FakeCompleter(VALID_RESPONSE)
    profile = refresh_style_profile(
        profile_name="default",
        blog_url="https://blog.naver.com/test",
        sample_texts=["포스트 1", "포스트 2"],
        completer=completer,
    )
    assert profile.structure_patterns == ["도입부에 개인 경험을 먼저 쓴다"]
    assert profile.frequent_expressions == ["완전 만족"]
    assert profile.review_conventions == ["첫인상 후 사용 경험 순"]
    assert profile.photo_usage_notes == ["사진 아래 짧은 감탄사"]


def test_refresh_raises_on_invalid_json() -> None:
    completer = FakeCompleter("이것은 JSON이 아닙니다")
    with pytest.raises(ValueError, match="invalid JSON"):
        refresh_style_profile(
            profile_name="default",
            blog_url="https://blog.naver.com/flowerbend",
            sample_texts=["포스트"],
            completer=completer,
        )


def test_refresh_raises_on_schema_invalid_json() -> None:
    bad_response = json.dumps({"structure_patterns": 42})
    completer = FakeCompleter(bad_response)
    with pytest.raises(ValueError, match="invalid style profile"):
        refresh_style_profile(
            profile_name="default",
            blog_url="https://blog.naver.com/flowerbend",
            sample_texts=["포스트"],
            completer=completer,
        )
