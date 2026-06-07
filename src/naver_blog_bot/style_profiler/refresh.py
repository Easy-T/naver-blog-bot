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


def refresh_style_profile(
    *,
    profile_name: str,
    blog_url: str,
    sample_texts: Sequence[str],
    completer: TextCompleter,
) -> StyleProfile:
    user_prompt = "샘플 블로그 포스트:\n\n" + "\n\n---\n\n".join(sample_texts)
    response = completer.complete_text(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        cacheable_context=(),
    )
    try:
        data = json.loads(response)
    except json.JSONDecodeError as exc:
        raise ValueError("Claude returned invalid JSON") from exc
    try:
        return StyleProfile(profile_name=profile_name, blog_url=blog_url, **data)
    except Exception as exc:
        raise ValueError("Claude returned an invalid style profile") from exc
