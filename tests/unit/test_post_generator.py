from datetime import datetime, timezone
from pathlib import Path

from naver_blog_bot.config import Settings
from naver_blog_bot.meme_library.models import MemeAsset, MemeIndex
from naver_blog_bot.post_generator.generator import PostGenerator, extract_title
from naver_blog_bot.style_profiler.models import StyleProfile


class FakeClaude:
    def __init__(self) -> None:
        self.last_call = None

    def complete_text(self, **kwargs: object) -> str:
        self.last_call = kwargs
        return "# 포포몬 체험단 후기\n\n사진을 보니 첫인상이 정말 좋았어요."


def test_extract_title_uses_first_markdown_heading() -> None:
    assert extract_title("# 포포몬 체험단 후기\n\n본문") == "포포몬 체험단 후기"


def test_extract_title_falls_back_for_empty_markdown() -> None:
    assert extract_title("\n\n") == "네이버 블로그 초안"


def test_post_generator_builds_draft_with_cacheable_context() -> None:
    fake = FakeClaude()
    now = datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc)
    settings = Settings(ogq_artwork_id="644e042a7d7f8")
    generator = PostGenerator(settings=settings, claude_client=fake, now=lambda: now)
    style_profile = StyleProfile(
        blog_url="https://blog.naver.com/flowerbend",
        updated_at=now,
        frequent_expressions=["완전 만족"],
        review_conventions=["첫인상 다음 사용 경험"],
    )
    meme_index = MemeIndex(
        updated_at=now,
        memes=[
            MemeAsset(
                id="satisfied",
                path=Path("assets/memes/satisfied.png"),
                tags=["satisfaction"],
                use_cases=["만족"],
                alt_text="만족하는 표정",
            )
        ],
    )

    draft = generator.generate(
        photo_paths=[Path("photos/one.jpg"), Path("photos/two.jpg")],
        memo="제품이 만족스럽고 사진은 두 장",
        style_profile=style_profile,
        meme_index=meme_index,
    )

    assert draft.id == "draft-20260503-120000"
    assert draft.title == "포포몬 체험단 후기"
    assert draft.memo == "제품이 만족스럽고 사진은 두 장"
    assert draft.photo_paths == [Path("photos/one.jpg"), Path("photos/two.jpg")]
    assert draft.selected_memes == [Path("assets/memes/satisfied.png")]
    assert draft.ogq_artwork_id == "644e042a7d7f8"
    assert "사진을 보니" in draft.body_markdown
    assert fake.last_call["system_prompt"].startswith("너는 네이버 블로그")
    assert "완전 만족" in fake.last_call["cacheable_context"][0]
    assert "satisfied.png" in fake.last_call["cacheable_context"][1]
    assert "제품이 만족스럽고 사진은 두 장" in fake.last_call["user_prompt"]
    assert "photos/one.jpg" in fake.last_call["user_prompt"]
