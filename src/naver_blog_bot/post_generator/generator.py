from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from naver_blog_bot.config import Settings
from naver_blog_bot.meme_library.models import MemeAsset, MemeIndex
from naver_blog_bot.post_generator.drafts import draft_id_from_time
from naver_blog_bot.post_generator.models import Draft
from naver_blog_bot.style_profiler.models import StyleProfile

SYSTEM_PROMPT = """너는 네이버 블로그 체험단 후기 초안을 작성하는 한국어 글쓰기 도우미다.
사용자의 기존 문체를 우선하고, 과장된 광고 문장보다 실제 사용 경험처럼 자연스럽게 쓴다.
사진 위치, OGQ 이모티콘, 짤방 후보는 초안에 사람이 검토할 수 있는 표시로 남긴다."""


class TextCompleter(Protocol):
    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        cacheable_context: Sequence[str],
    ) -> str: ...


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
    ) -> Draft:
        selected_memes = meme_index.candidates_for_memo(memo)
        body_markdown = self.claude_client.complete_text(
            system_prompt=SYSTEM_PROMPT,
            cacheable_context=[
                style_profile.to_cache_text(),
                meme_index.to_cache_text(),
            ],
            user_prompt=self._build_user_prompt(photo_paths, memo, selected_memes),
        )
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
        self, photo_paths: list[Path], memo: str, selected_memes: list[MemeAsset]
    ) -> str:
        photos = "\n".join(f"- {path}" for path in photo_paths)
        memes = (
            "\n".join(
                f"- {meme.id}: {meme.path} ({', '.join(meme.use_cases)})"
                for meme in selected_memes
            )
            or "- 선택된 짤방 없음"
        )
        return f"""다음 메모와 사진 목록을 바탕으로 네이버 블로그 초안을 작성해줘.

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
- OGQ를 넣을 위치는 `[OGQ: {self.settings.ogq_name}]` 형식으로 표시
- 짤방을 넣을 위치는 `[짤방: 파일경로]` 형식으로 표시
"""
