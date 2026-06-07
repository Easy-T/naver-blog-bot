from pathlib import Path

from naver_blog_bot.meme_harvester.service import _parse_classification, classify_image


def test_parse_classification_reads_is_meme_and_fields() -> None:
    raw = (
        '{"is_meme": true, "tags": ["놀람"], '
        '"use_cases": ["반전 강조"], "alt_text": "놀란 강아지"}'
    )
    data = _parse_classification(raw)
    assert data["is_meme"] is True
    assert data["tags"] == ["놀람"]
    assert data["use_cases"] == ["반전 강조"]
    assert data["alt_text"] == "놀란 강아지"


def test_parse_classification_defaults_when_garbage() -> None:
    data = _parse_classification("not json")
    assert data["is_meme"] is False
    assert data["tags"] == []


def test_classify_image_passes_context_into_prompt(tmp_path: Path) -> None:
    img = tmp_path / "m.jpg"
    img.write_bytes(b"x")
    seen = {}

    class FakeVision:
        def complete_vision(self, *, image_path, prompt):
            seen["prompt"] = prompt
            return '{"is_meme": true, "tags": ["웃음"], "use_cases": ["유머"], "alt_text": "ㅋㅋ"}'

    data = classify_image(img, FakeVision(), context="너무 웃겨서 빵 터졌어요")
    assert data["is_meme"] is True
    assert "너무 웃겨서 빵 터졌어요" in seen["prompt"]


def test_harvest_memes_dedupes_by_hash_and_counts_frequency(tmp_path: Path) -> None:
    from naver_blog_bot.blog_scraper.models import ImageBlock, PostDocument, TextBlock
    from naver_blog_bot.meme_harvester.service import harvest_memes

    doc1 = PostDocument(
        url="https://m.blog.naver.com/f/1",
        title="t1",
        blocks=[
            TextBlock(content="웃긴 일이 있었어요"),
            ImageBlock(alt="", src="https://cdn/a.jpg"),
            ImageBlock(alt="", src="https://cdn/photo.jpg"),
        ],
    )
    doc2 = PostDocument(
        url="https://m.blog.naver.com/f/2",
        title="t2",
        blocks=[
            ImageBlock(alt="", src="https://cdn/b.jpg"),
        ],
    )

    bytes_by_url = {
        "https://cdn/a.jpg": b"MEME-BYTES",
        "https://cdn/b.jpg": b"MEME-BYTES",
        "https://cdn/photo.jpg": b"REAL-PHOTO-BYTES",
    }
    fetch_calls: list[str] = []

    def fake_fetch(url: str, *, referer: str) -> bytes:
        fetch_calls.append(url)
        return bytes_by_url[url]

    class FakeVision:
        def __init__(self) -> None:
            self.calls = 0

        def complete_vision(self, *, image_path, prompt):
            self.calls += 1
            data = image_path.read_bytes()
            if data == b"MEME-BYTES":
                return '{"is_meme": true, "tags": ["웃음"], "use_cases": ["유머"], "alt_text": "ㅋㅋ"}'
            return '{"is_meme": false, "tags": [], "use_cases": [], "alt_text": "사진"}'

    vision = FakeVision()
    cache = tmp_path / ".harvest-cache.json"
    result = harvest_memes(
        [doc1, doc2],
        vision,
        memes_dir=tmp_path / "memes",
        cache_path=cache,
        fetch=fake_fetch,
    )

    assert len(result.assets) == 1
    asset = result.assets[0]
    assert asset.frequency == 2
    assert "웃음" in asset.tags
    assert asset.path.exists()
    assert sorted(result.meme_srcs) == ["https://cdn/a.jpg", "https://cdn/b.jpg"]
    assert len(fetch_calls) == 3
    assert vision.calls == 2


def test_harvest_memes_cache_hit_skips_fetch_and_vision(tmp_path: Path) -> None:
    from naver_blog_bot.blog_scraper.models import ImageBlock, PostDocument
    from naver_blog_bot.meme_harvester.service import harvest_memes

    doc = PostDocument(
        url="https://m.blog.naver.com/f/1",
        title="t",
        blocks=[
            ImageBlock(alt="", src="https://cdn/a.jpg"),
        ],
    )

    def fetch_once(url: str, *, referer: str) -> bytes:
        return b"MEME"

    class V:
        def __init__(self) -> None:
            self.calls = 0

        def complete_vision(self, *, image_path, prompt):
            self.calls += 1
            return (
                '{"is_meme": true, "tags": ["x"], "use_cases": ["y"], "alt_text": "z"}'
            )

    cache = tmp_path / ".harvest-cache.json"
    v1 = V()
    harvest_memes(
        [doc], v1, memes_dir=tmp_path / "m", cache_path=cache, fetch=fetch_once
    )
    assert v1.calls == 1

    fetch_calls: list[str] = []

    def fetch_track(url: str, *, referer: str) -> bytes:
        fetch_calls.append(url)
        return b"MEME"

    v2 = V()
    result2 = harvest_memes(
        [doc], v2, memes_dir=tmp_path / "m", cache_path=cache, fetch=fetch_track
    )
    assert v2.calls == 0
    assert fetch_calls == []
    assert len(result2.assets) == 1


def test_harvest_memes_skips_download_failures(tmp_path: Path) -> None:
    from naver_blog_bot.blog_scraper.models import ImageBlock, PostDocument
    from naver_blog_bot.meme_harvester.service import harvest_memes

    doc = PostDocument(
        url="https://m.blog.naver.com/f/1",
        title="t",
        blocks=[
            ImageBlock(alt="", src="https://cdn/broken.jpg"),
        ],
    )

    def failing_fetch(url: str, *, referer: str):
        return None

    class V:
        def complete_vision(self, *, image_path, prompt):
            raise AssertionError("should not classify a failed download")

    result = harvest_memes(
        [doc],
        V(),
        memes_dir=tmp_path / "m",
        cache_path=tmp_path / "c.json",
        fetch=failing_fetch,
    )
    assert result.assets == []
    assert result.meme_srcs == []
