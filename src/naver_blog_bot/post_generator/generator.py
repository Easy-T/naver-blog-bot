from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from naver_blog_bot.config import Settings
from naver_blog_bot.meme_library.models import MemeAsset, MemeIndex
from naver_blog_bot.post_generator.drafts import draft_id_from_time
from naver_blog_bot.post_generator.models import Draft
from naver_blog_bot.shared.protocols import TextCompleter
from naver_blog_bot.style_profiler.examples import ExamplePost
from naver_blog_bot.style_profiler.models import StyleProfile

SYSTEM_PROMPT = """너는 네이버 블로그 체험단 후기 초안을 작성하는 한국어 글쓰기 도우미다.
사용자의 기존 문체를 우선하고, 과장된 광고 문장보다 실제 사용 경험처럼 자연스럽게 쓴다.
사진 위치, 이모티콘 의도, 짤방 후보는 초안에 사람이 검토할 수 있는 표시로 남긴다.
이모티콘 위치는 캐시 컨텍스트의 emoticon_usage_patterns에서 학습한 패턴을 따른다. 모든 문단에 강제로 넣지 않는다."""

MEME_PLACEMENT_SYSTEM = """너는 한국어 블로그 편집자다.
초안과 짤방 목록을 보고, 각 짤방이 자연스럽게 어울리는 문단 바로 다음 줄에 [짤방: {id}] 마커를 삽입해라.
규칙:
- 억지로 넣지 마라. 정말 어울리는 곳에만.
- 짤방 하나는 한 번만 사용.
- 마커 외 본문 텍스트는 절대 수정하지 마라.
- 수정된 초안 전체만 반환해라."""


def extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:80]
    return "네이버 블로그 초안"


class PostGenerator:
    def __init__(
        self,
        *,
        settings: Settings,
        claude_client: TextCompleter,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.claude_client = claude_client
        self.now = now or (lambda: datetime.now(timezone.utc))

    def generate(
        self,
        *,
        photo_paths: list[Path],
        memo: str,
        style_profile: StyleProfile,
        meme_index: MemeIndex,
        examples: list[ExamplePost] | None = None,
    ) -> Draft:
        selected_memes = meme_index.candidates_for_memo(memo)
        body_markdown = self.claude_client.complete_text(
            system_prompt=SYSTEM_PROMPT,
            cacheable_context=[
                style_profile.to_cache_text(),
                meme_index.to_cache_text(),
            ],
            user_prompt=self._build_user_prompt(photo_paths, memo, selected_memes, examples),
        )
        body_markdown = self._place_memes_in_draft(body_markdown, meme_index)
        created_at = self.now()
        return Draft(
            id=draft_id_from_time(created_at),
            title=extract_title(body_markdown),
            memo=memo,
            body_markdown=body_markdown,
            photo_paths=photo_paths,
            selected_memes=[meme.path for meme in selected_memes],
            ogq_artwork_id=self.settings.ogq_artwork_id,
            created_at=created_at,
        )

    def _build_user_prompt(
        self,
        photo_paths: list[Path],
        memo: str,
        selected_memes: list[MemeAsset],
        examples: list[ExamplePost] | None,
    ) -> str:
        photos = "\n".join(f"- {path}" for path in photo_paths)
        memes = (
            "\n".join(
                f"- {meme.id}: {meme.path} ({', '.join(meme.use_cases)})"
                for meme in selected_memes
            )
            or "- 선택된 짤방 없음"
        )

        examples_section = ""
        if examples:
            parts = []
            for i, ex in enumerate(examples, start=1):
                parts.append(f"[예시 {i}] {ex.title}\n{ex.structured_text}")
            examples_section = "\n\n참고 예시 포스트 (문체 참고용):\n" + "\n\n".join(parts)

        return f"""다음 메모와 사진 목록을 바탕으로 네이버 블로그 초안을 작성해줘.{examples_section}

메모:
{memo}

사진 경로:
{photos}

사용 가능한 OGQ 이모티콘:
- artworkId: {self.settings.ogq_artwork_id}
- name: {self.settings.ogq_name}

추천 짤방 후보:
{memes}

출력 형식:
- 첫 줄은 마크다운 H1 제목으로 작성
- 본문은 한국어 마크다운으로 작성
- 사진을 넣을 위치는 `[사진: 파일경로]` 형식으로 표시
- 이모티콘을 넣을 위치는 `{{{{이모티콘:감정유형}}}}` 형식으로 표시 (예: `{{{{이모티콘:만족}}}}`, `{{{{이모티콘:감탄}}}}`, `{{{{이모티콘:마무리}}}}`)
- 짤방을 넣을 위치는 `[짤방: meme_id]` 형식으로 표시
"""

    def _place_memes_in_draft(self, body: str, meme_index: MemeIndex) -> str:
        if not meme_index.memes:
            return body
        meme_list = "\n".join(
            f"- id: {m.id}, use_cases: {', '.join(m.use_cases)}, tags: {', '.join(m.tags)}"
            for m in meme_index.memes
        )
        user_prompt = f"초안:\n\n{body}\n\n짤방 목록:\n{meme_list}"
        return self.claude_client.complete_text(
            system_prompt=MEME_PLACEMENT_SYSTEM,
            user_prompt=user_prompt,
            cacheable_context=[],
        )
