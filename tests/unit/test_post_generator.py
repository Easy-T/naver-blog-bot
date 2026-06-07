from datetime import datetime, timezone
from pathlib import Path

from naver_blog_bot.config import Settings
from naver_blog_bot.meme_library.models import MemeAsset, MemeIndex
from naver_blog_bot.post_generator.generator import PostGenerator, extract_title
from naver_blog_bot.style_profiler.examples import ExamplePost
from naver_blog_bot.style_profiler.models import StyleProfile


class FakeClaude:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def complete_text(self, **kwargs: object) -> str:
        self.calls.append(dict(kwargs))
        if len(self.calls) == 1:
            return "# 포포몬 체험단 후기\n\n사진을 보니 첫인상이 정말 좋았어요."
        # 2nd call (meme placement): return body extracted from user_prompt
        user_prompt = str(kwargs.get("user_prompt", ""))
        if "초안:\n\n" in user_prompt and "\n\n짤방 목록:" in user_prompt:
            return user_prompt.split("초안:\n\n")[1].split("\n\n짤방 목록:")[0]
        return user_prompt


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
        emoticon_usage_patterns=["만족감 표현 시 이모티콘 사용", "문단 끝 강조에 활용"],
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
    assert fake.calls[0]["system_prompt"].startswith("너는 네이버 블로그")
    assert "완전 만족" in fake.calls[0]["cacheable_context"][0]
    assert "만족감 표현 시 이모티콘 사용" in fake.calls[0]["cacheable_context"][0]
    assert "satisfied.png" in fake.calls[0]["cacheable_context"][1]
    assert "제품이 만족스럽고 사진은 두 장" in fake.calls[0]["user_prompt"]
    assert "photos/one.jpg" in fake.calls[0]["user_prompt"]
    assert "{{이모티콘:감정유형}}" in fake.calls[0]["user_prompt"]
    assert "{{이모티콘:만족}}" in fake.calls[0]["user_prompt"]
    assert settings.ogq_artwork_id in fake.calls[0]["user_prompt"]
    assert "emoticon_usage_patterns" in fake.calls[0]["system_prompt"]
    assert "학습한 패턴" in fake.calls[0]["system_prompt"]
    assert "모든 문단" in fake.calls[0]["system_prompt"]
    assert "강제로 넣지 않는다" in fake.calls[0]["system_prompt"]


def test_post_generator_injects_few_shot_examples() -> None:
    fake = FakeClaude()
    now = datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc)
    settings = Settings()
    generator = PostGenerator(settings=settings, claude_client=fake, now=lambda: now)
    style_profile = StyleProfile(blog_url="https://blog.naver.com/flowerbend")
    meme_index = MemeIndex()
    examples = [
        ExamplePost(
            title="카페 후기",
            url="https://blog.naver.com/flowerbend/1",
            structured_text="오늘 카페 정말 좋았어요.",
        )
    ]

    generator.generate(
        photo_paths=[Path("photos/a.jpg")],
        memo="카페 방문",
        style_profile=style_profile,
        meme_index=meme_index,
        examples=examples,
    )

    assert "카페 후기" in fake.calls[0]["user_prompt"]
    assert "오늘 카페 정말 좋았어요." in fake.calls[0]["user_prompt"]
    assert "참고 예시" in fake.calls[0]["user_prompt"]


def test_post_generator_works_without_examples() -> None:
    fake = FakeClaude()
    now = datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc)
    settings = Settings()
    generator = PostGenerator(settings=settings, claude_client=fake, now=lambda: now)
    style_profile = StyleProfile(blog_url="https://blog.naver.com/flowerbend")
    meme_index = MemeIndex()

    draft = generator.generate(
        photo_paths=[Path("photos/a.jpg")],
        memo="테스트",
        style_profile=style_profile,
        meme_index=meme_index,
        examples=None,
    )

    assert draft.body_markdown


def test_place_memes_in_draft_inserts_markers() -> None:
    class MarkerClaude:
        def complete_text(self, **kwargs):
            return "# 제목\n\n좋았어요.\n[짤방: satisfied]\n\n마무리."

    settings = Settings()
    generator = PostGenerator(settings=settings, claude_client=MarkerClaude())
    meme_index = MemeIndex(
        memes=[
            MemeAsset(
                id="satisfied",
                path=Path("assets/memes/satisfied.png"),
                tags=["만족"],
                use_cases=["만족 표현"],
                alt_text="만족",
            )
        ]
    )
    body = "# 제목\n\n좋았어요.\n\n마무리."

    result = generator._place_memes_in_draft(body, meme_index)

    assert "[짤방: satisfied]" in result


def test_place_memes_skips_when_no_memes() -> None:
    class NeverCalled:
        def complete_text(self, **kwargs):
            raise AssertionError("should not be called")

    settings = Settings()
    generator = PostGenerator(settings=settings, claude_client=NeverCalled())
    body = "본문입니다."

    result = generator._place_memes_in_draft(body, MemeIndex())

    assert result == "본문입니다."


class FakeVisionClaude(FakeClaude):
    def __init__(self) -> None:
        super().__init__()
        self.vision_calls = 0

    def complete_vision(self, *, image_path, prompt) -> str:
        self.vision_calls += 1
        return '{"caption": "파란 MUTO TAILOR 간판", "category": "외관"}'


def _make_photo(p: Path) -> None:
    from PIL import Image

    Image.new("RGB", (640, 480), (10, 20, 30)).save(p, "JPEG")


def test_generate_uses_vision_captions_in_prompt(tmp_path: Path) -> None:
    photo = tmp_path / "26.jpg"
    _make_photo(photo)
    fake = FakeVisionClaude()
    now = datetime(2026, 6, 7, 12, 0, 0, tzinfo=timezone.utc)
    settings = Settings(drafts_dir=tmp_path / "drafts")
    generator = PostGenerator(settings=settings, claude_client=fake, now=lambda: now)

    generator.generate(
        photo_paths=[photo],
        memo="테일러샵 방문",
        style_profile=StyleProfile(blog_url="https://blog.naver.com/flowerbend"),
        meme_index=MemeIndex(),
    )

    assert fake.vision_calls == 1
    assert "파란 MUTO TAILOR 간판" in fake.calls[0]["user_prompt"]


def test_generate_no_vision_skips_vision(tmp_path: Path) -> None:
    photo = tmp_path / "26.jpg"
    _make_photo(photo)
    fake = FakeVisionClaude()
    now = datetime(2026, 6, 7, 12, 0, 0, tzinfo=timezone.utc)
    settings = Settings(drafts_dir=tmp_path / "drafts")
    generator = PostGenerator(settings=settings, claude_client=fake, now=lambda: now)

    generator.generate(
        photo_paths=[photo],
        memo="테일러샵 방문",
        style_profile=StyleProfile(blog_url="https://blog.naver.com/flowerbend"),
        meme_index=MemeIndex(),
        use_vision=False,
    )

    assert fake.vision_calls == 0
    assert str(photo) in fake.calls[0]["user_prompt"]


def test_generate_falls_back_to_top_frequency_when_memo_no_match() -> None:
    fake = FakeClaude()
    now = datetime(2026, 6, 7, 12, 0, 0, tzinfo=timezone.utc)
    settings = Settings()
    generator = PostGenerator(settings=settings, claude_client=fake, now=lambda: now)
    style_profile = StyleProfile(blog_url="https://blog.naver.com/flowerbend")
    meme_index = MemeIndex(
        memes=[
            MemeAsset(
                id="popular",
                path=Path("a.png"),
                tags=["없음매칭"],
                use_cases=["전혀안겹침"],
                alt_text="x",
                frequency=9,
            ),
            MemeAsset(
                id="rare",
                path=Path("b.png"),
                tags=["딴거"],
                use_cases=["딴상황"],
                alt_text="y",
                frequency=1,
            ),
        ]
    )

    generator.generate(
        photo_paths=[Path("p.jpg")],
        memo="메모에는 태그가 전혀 안 들어있음",
        style_profile=style_profile,
        meme_index=meme_index,
        use_vision=False,
    )
    assert "popular" in fake.calls[0]["user_prompt"]
