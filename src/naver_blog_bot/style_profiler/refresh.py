import json
from collections.abc import Sequence

from naver_blog_bot.shared.protocols import TextCompleter
from naver_blog_bot.style_profiler.models import StyleProfile

SYSTEM_PROMPT = """너는 한국어 블로그 포스트의 문체 분석가다.
제공된 샘플 포스트에서 재사용 가능한 안정적인 문체 특성을 추출해라.
포스트 내용을 요약하지 말고, 같은 문체로 다시 쓸 때 도움이 되는 반복 패턴에 집중해라.

샘플의 [사진]·[이미지]·[짤방]·[이모티콘:설명] 마커는 배치 빈도·스타일 신호로만 분석해라(내용 요약 금지).
특히 [짤방](반응용 밈/움짤)이 어떤 흐름·상황에서 등장하는지를 meme_usage_patterns로 정리해라.

다음 필드를 가진 JSON 객체만 반환해라:
{
  "structure_patterns": [...],
  "tone_keywords": [...],
  "frequent_expressions": [...],
  "review_conventions": [...],
  "photo_usage_notes": [...],
  "emoticon_usage_patterns": [...],
  "meme_usage_patterns": [...]
}

각 리스트는 3-8개의 간결한 한국어 문자열을 포함해야 한다. JSON 외의 다른 텍스트는 반환하지 마라."""

MERGE_PROMPT = """너는 여러 부분 문체 프로필(JSON)을 하나로 통합하는 편집자다.
같은 의미의 항목은 합치고 중복은 제거해, 블로그 전체를 대표하는 안정적 패턴만 남겨라.
입력과 동일한 7개 키를 가진 JSON 객체만 반환해라. 각 리스트는 3-8개. JSON 외 텍스트 금지.
키: structure_patterns, tone_keywords, frequent_expressions, review_conventions,
photo_usage_notes, emoticon_usage_patterns, meme_usage_patterns"""


def _complete_profile_json(
    completer: TextCompleter, system_prompt: str, user_prompt: str
) -> dict:
    response = completer.complete_text(
        system_prompt=system_prompt, user_prompt=user_prompt, cacheable_context=()
    )
    try:
        data = json.loads(response)
    except json.JSONDecodeError as exc:
        raise ValueError("Claude returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Claude returned invalid JSON")
    return data


def refresh_style_profile(
    *,
    profile_name: str,
    blog_url: str,
    sample_texts: Sequence[str],
    completer: TextCompleter,
    batch_size: int = 12,
) -> StyleProfile:
    texts = list(sample_texts)
    if len(texts) <= batch_size:
        user_prompt = "샘플 블로그 포스트:\n\n" + "\n\n---\n\n".join(texts)
        data = _complete_profile_json(completer, SYSTEM_PROMPT, user_prompt)
    else:
        partials: list[str] = []
        for start in range(0, len(texts), batch_size):
            chunk = texts[start : start + batch_size]
            user_prompt = "샘플 블로그 포스트:\n\n" + "\n\n---\n\n".join(chunk)
            partial = completer.complete_text(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                cacheable_context=(),
            )
            partials.append(partial)
        merge_input = "부분 프로필들:\n\n" + "\n\n---\n\n".join(partials)
        data = _complete_profile_json(completer, MERGE_PROMPT, merge_input)
    try:
        return StyleProfile(profile_name=profile_name, blog_url=blog_url, **data)
    except Exception as exc:
        raise ValueError("Claude returned an invalid style profile") from exc
