from types import SimpleNamespace

from naver_blog_bot.config import Settings
from naver_blog_bot.shared.claude_client import ClaudeTextClient


class FakeMessages:
    def __init__(self) -> None:
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="생성된 본문")])


class FakeAnthropic:
    def __init__(self) -> None:
        self.messages = FakeMessages()


def test_complete_text_uses_configured_model_and_cache_blocks() -> None:
    fake = FakeAnthropic()
    settings = Settings(claude_model="claude-opus-4-7", claude_max_tokens=1234)
    client = ClaudeTextClient(settings=settings, anthropic_client=fake)

    text = client.complete_text(
        system_prompt="너는 블로그 글쓰기 도우미다.",
        cacheable_context=["style profile", "meme index"],
        user_prompt="메모로 초안을 작성해줘.",
    )

    assert text == "생성된 본문"
    assert fake.messages.last_kwargs["model"] == "claude-opus-4-7"
    assert fake.messages.last_kwargs["max_tokens"] == 1234
    assert fake.messages.last_kwargs["thinking"] == {"type": "adaptive"}
    assert fake.messages.last_kwargs["messages"] == [
        {"role": "user", "content": "메모로 초안을 작성해줘."}
    ]
    assert fake.messages.last_kwargs["system"] == [
        {"type": "text", "text": "너는 블로그 글쓰기 도우미다."},
        {"type": "text", "text": "style profile", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "meme index", "cache_control": {"type": "ephemeral"}},
    ]


def test_complete_text_accepts_dict_text_blocks_from_fake_clients() -> None:
    class DictMessages:
        def create(self, **kwargs):
            return SimpleNamespace(content=[{"type": "text", "text": "딕셔너리 본문"}])

    fake = SimpleNamespace(messages=DictMessages())
    client = ClaudeTextClient(settings=Settings(), anthropic_client=fake)

    assert client.complete_text(system_prompt="system", user_prompt="user") == "딕셔너리 본문"
