import json
import pytest
from collections.abc import Sequence

from naver_blog_bot.style_profiler.models import StyleProfile
from naver_blog_bot.style_profiler.refresh import refresh_style_profile


class FakeCompleter:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_system_prompt: str = ""

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        cacheable_context: Sequence[str] = (),
    ) -> str:
        self.last_system_prompt = system_prompt
        return self._response


VALID_RESPONSE = json.dumps(
    {
        "structure_patterns": ["도입부에 개인 경험을 먼저 쓴다"],
        "tone_keywords": ["다정함", "솔직함"],
        "frequent_expressions": ["완전 만족"],
        "review_conventions": ["첫인상 후 사용 경험 순"],
        "photo_usage_notes": ["사진 아래 짧은 감탄사"],
        "emoticon_usage_patterns": ["단락 끝마다 이모티콘 1개"],
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
    assert profile.emoticon_usage_patterns == ["단락 끝마다 이모티콘 1개"]


def test_system_prompt_requests_emoticon_usage_patterns() -> None:
    completer = FakeCompleter(VALID_RESPONSE)
    refresh_style_profile(
        profile_name="default",
        blog_url="https://blog.naver.com/test",
        sample_texts=["[이모티콘:기쁨] 맛있었어요"],
        completer=completer,
    )
    assert "emoticon_usage_patterns" in completer.last_system_prompt
    assert "[이모티콘" in completer.last_system_prompt


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


def test_system_prompt_requests_meme_usage_patterns() -> None:
    completer = FakeCompleter(VALID_RESPONSE)
    refresh_style_profile(
        profile_name="default",
        blog_url="https://blog.naver.com/test",
        sample_texts=["[짤방] 빵 터졌어요"],
        completer=completer,
    )
    assert "meme_usage_patterns" in completer.last_system_prompt
    assert "[짤방]" in completer.last_system_prompt


def test_refresh_parses_meme_usage_patterns() -> None:
    response = json.dumps(
        {
            "structure_patterns": ["a"],
            "tone_keywords": ["b"],
            "frequent_expressions": ["c"],
            "review_conventions": ["d"],
            "photo_usage_notes": ["e"],
            "emoticon_usage_patterns": ["f"],
            "meme_usage_patterns": ["반전 직후 짤방"],
        }
    )
    completer = FakeCompleter(response)
    profile = refresh_style_profile(
        profile_name="flowerbend",
        blog_url="https://blog.naver.com/flowerbend",
        sample_texts=["[짤방] 반전!"],
        completer=completer,
    )
    assert profile.meme_usage_patterns == ["반전 직후 짤방"]


class RecordingCompleter:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls: list[str] = []

    def complete_text(self, *, system_prompt, user_prompt, cacheable_context=()):
        self.calls.append(user_prompt)
        return self._responses[len(self.calls) - 1]


def _axis_json(tag: str) -> str:
    return json.dumps(
        {
            "structure_patterns": [f"s-{tag}"],
            "tone_keywords": [f"t-{tag}"],
            "frequent_expressions": [f"e-{tag}"],
            "review_conventions": [f"r-{tag}"],
            "photo_usage_notes": [f"p-{tag}"],
            "emoticon_usage_patterns": [f"em-{tag}"],
            "meme_usage_patterns": [f"m-{tag}"],
        }
    )


def test_refresh_batches_large_corpus_then_merges() -> None:
    merged = _axis_json("MERGED")
    completer = RecordingCompleter(
        [_axis_json("1"), _axis_json("2"), _axis_json("3"), merged]
    )
    profile = refresh_style_profile(
        profile_name="flowerbend",
        blog_url="https://blog.naver.com/flowerbend",
        sample_texts=[f"포스트 {i}" for i in range(5)],
        completer=completer,
        batch_size=2,
    )
    assert len(completer.calls) == 4
    assert profile.tone_keywords == ["t-MERGED"]
    assert "s-1" in completer.calls[-1] and "s-3" in completer.calls[-1]


def test_refresh_single_call_when_under_batch_size() -> None:
    completer = FakeCompleter(VALID_RESPONSE)
    refresh_style_profile(
        profile_name="default",
        blog_url="https://blog.naver.com/flowerbend",
        sample_texts=["a", "b"],
        completer=completer,
        batch_size=12,
    )
    assert "meme_usage_patterns" in completer.last_system_prompt
