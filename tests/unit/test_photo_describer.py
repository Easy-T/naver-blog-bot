from pathlib import Path

from PIL import Image

from naver_blog_bot.photo_describer.models import PhotoCaption
from naver_blog_bot.photo_describer.service import (
    _parse_caption,
    _prepare_image,
    describe_photos,
)


def _make_jpg(path: Path, size: tuple[int, int]) -> None:
    Image.new("RGB", size, (123, 200, 100)).save(path, "JPEG")


class FakeVision:
    def __init__(self, reply: str = '{"caption": "설명", "category": "내부"}') -> None:
        self.reply = reply
        self.calls = 0

    def complete_vision(self, *, image_path: Path, prompt: str) -> str:
        self.calls += 1
        return self.reply


class BoomVision:
    def complete_vision(self, *, image_path: Path, prompt: str) -> str:
        raise RuntimeError("vision down")


def test_photo_caption_defaults() -> None:
    c = PhotoCaption(path=Path("a.jpg"))
    assert c.path == Path("a.jpg")
    assert c.caption == ""
    assert c.category == "기타"


def test_parse_caption_json() -> None:
    c = _parse_caption(Path("x.jpg"), '{"caption": "파란 간판", "category": "외관"}')
    assert c.caption == "파란 간판"
    assert c.category == "외관"


def test_parse_caption_unknown_category_falls_back() -> None:
    c = _parse_caption(Path("x.jpg"), '{"caption": "뭔가", "category": "음식"}')
    assert c.category == "기타"


def test_parse_caption_plain_text_fallback() -> None:
    c = _parse_caption(Path("x.jpg"), "그냥 텍스트 설명")
    assert c.caption == "그냥 텍스트 설명"
    assert c.category == "기타"


def test_prepare_image_downscales_large(tmp_path: Path) -> None:
    src = tmp_path / "big.jpg"
    _make_jpg(src, (3000, 2000))
    out = _prepare_image(src, tmp_path / "work")
    with Image.open(out) as im:
        assert max(im.size) <= 1024


def test_prepare_image_falls_back_on_bad_file(tmp_path: Path) -> None:
    bad = tmp_path / "notimage.jpg"
    bad.write_text("not an image", encoding="utf-8")
    out = _prepare_image(bad, tmp_path / "work")
    assert out == bad


def test_describe_photos_returns_captions(tmp_path: Path) -> None:
    src = tmp_path / "p.jpg"
    _make_jpg(src, (800, 600))
    fake = FakeVision()
    out = describe_photos([src], fake, cache_path=tmp_path / "cache.json")
    assert out[0].caption == "설명"
    assert out[0].category == "내부"
    assert fake.calls == 1


def test_describe_photos_uses_cache(tmp_path: Path) -> None:
    src = tmp_path / "p.jpg"
    _make_jpg(src, (800, 600))
    cache = tmp_path / "cache.json"
    first = FakeVision()
    describe_photos([src], first, cache_path=cache)
    second = FakeVision()
    out = describe_photos([src], second, cache_path=cache)
    assert second.calls == 0
    assert out[0].caption == "설명"


def test_describe_photos_falls_back_on_error(tmp_path: Path) -> None:
    src = tmp_path / "p.jpg"
    _make_jpg(src, (800, 600))
    out = describe_photos([src], BoomVision(), cache_path=tmp_path / "c.json")
    assert out[0].caption == ""
    assert out[0].category == "기타"
