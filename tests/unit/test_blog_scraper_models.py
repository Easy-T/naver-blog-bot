from naver_blog_bot.blog_scraper.models import (
    EmoticonBlock,
    ImageBlock,
    PostDocument,
    TextBlock,
)


def test_structured_text_preserves_title_and_block_order() -> None:
    document = PostDocument(
        url="https://m.blog.naver.com/myid/223456789",
        title="포포몬 첫 사용 후기",
        blocks=[
            TextBlock(content="오늘 드디어 써봤는데요."),
            ImageBlock(alt="제품 사진"),
            TextBlock(content="첫인상은 생각보다 훨씬 좋았어요!"),
            EmoticonBlock(description="만족하는 표정"),
            ImageBlock(),
            ImageBlock(),
            EmoticonBlock(description="엄지척"),
        ],
    )

    assert document.to_structured_text() == "\n".join(
        [
            "제목: 포포몬 첫 사용 후기",
            "",
            "오늘 드디어 써봤는데요.",
            "[이미지]",
            "첫인상은 생각보다 훨씬 좋았어요!",
            "[이모티콘:만족하는 표정]",
            "[이미지]",
            "[이미지]",
            "[이모티콘:엄지척]",
        ]
    )


def test_structured_text_skips_empty_text_blocks() -> None:
    document = PostDocument(
        url="https://example.com/post",
        blocks=[
            TextBlock(content="  "),
            TextBlock(content="본문"),
            EmoticonBlock(),
        ],
    )

    assert document.to_structured_text() == "본문\n[이모티콘]"


def test_structured_text_without_title_has_no_leading_blank_line() -> None:
    document = PostDocument(
        url="https://example.com/post",
        blocks=[ImageBlock(), TextBlock(content="마무리")],
    )

    assert document.to_structured_text() == "[이미지]\n마무리"


def test_to_annotated_text_marks_memes_and_photos() -> None:
    from naver_blog_bot.blog_scraper.models import (
        EmoticonBlock,
        ImageBlock,
        PostDocument,
        TextBlock,
    )

    doc = PostDocument(
        url="https://m.blog.naver.com/f/1",
        title="제목",
        blocks=[
            TextBlock(content="웃긴 일"),
            ImageBlock(alt="", src="https://cdn/meme.gif"),
            ImageBlock(alt="", src="https://cdn/photo.jpg"),
            EmoticonBlock(description="기쁨"),
        ],
    )
    text = doc.to_annotated_text({"https://cdn/meme.gif"})
    lines = text.splitlines()
    assert "[짤방]" in lines
    assert "[사진]" in lines
    assert "[이모티콘:기쁨]" in lines
    assert text.count("[짤방]") == 1
    assert text.count("[사진]") == 1
