import base64
import io
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from naver_blog_bot.post_generator.models import Draft, _EXIF_ORIENTATION_TAG

# 1x1 PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


def _make_draft(body: str) -> Draft:
    return Draft(
        id="draft-20260529-120000",
        title="테스트 초안",
        memo="테스트 메모",
        body_markdown=body,
        photo_paths=[Path("photos/a.jpg")],
        created_at=datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_to_html_contains_title() -> None:
    draft = _make_draft("# 제목\n\n본문입니다.")
    html = draft.to_html()
    assert "테스트 초안" in html
    assert "<h1>" in html


def test_to_html_renders_photo_placeholder() -> None:
    # Non-existent path -> placeholder div (back-compat).
    draft = _make_draft("[사진: photos/a.jpg]")
    html = draft.to_html()
    assert '<div class="photo-placeholder">' in html
    assert "photos/a.jpg" in html


def test_to_html_renders_emoticon_badge() -> None:
    draft = _make_draft("재미있었어요. {{이모티콘:기쁨}}")
    html = draft.to_html()
    assert "emoticon-badge" in html
    assert "기쁨" in html


def test_to_html_renders_meme_placeholder() -> None:
    draft = _make_draft("[짤방: satisfied]")
    html = draft.to_html()
    assert '<div class="meme-placeholder">' in html
    assert "satisfied" in html


def test_to_html_escapes_html_special_chars() -> None:
    draft = _make_draft("A < B & C > D")
    html = draft.to_html()
    assert "&lt;" in html
    assert "&amp;" in html
    assert "&gt;" in html


def test_to_html_is_valid_html_structure() -> None:
    draft = _make_draft("본문")
    html = draft.to_html()
    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="ko">' in html
    assert "</html>" in html


# --- Cycle 11: base64 image rendering ---
# Note: the CSS block always defines `.photo-placeholder`/`.meme-placeholder`,
# so distinguish a real render from a placeholder by the `<div class=...>` tag,
# not by the bare class name.


def test_to_html_embeds_real_photo_as_base64(tmp_path: Path) -> None:
    img = tmp_path / "a.png"
    img.write_bytes(_PNG)
    html = _make_draft(f"[사진: {img}]").to_html()
    assert '<img class="photo"' in html
    assert "data:image/png;base64," in html
    assert '<div class="photo-placeholder">' not in html


def test_to_html_missing_photo_keeps_placeholder() -> None:
    html = _make_draft("[사진: /definitely/not/here.jpg]").to_html()
    assert '<div class="photo-placeholder">' in html
    assert '<img class="photo"' not in html


def test_to_html_embeds_meme_via_meme_paths(tmp_path: Path) -> None:
    meme = tmp_path / "m.png"
    meme.write_bytes(_PNG)
    html = _make_draft("[짤방: m1]").to_html({"m1": meme})
    assert '<img class="meme"' in html
    assert "data:image/png;base64," in html
    assert '<div class="meme-placeholder">' not in html


def test_to_html_unknown_meme_id_keeps_placeholder(tmp_path: Path) -> None:
    meme = tmp_path / "m.png"
    meme.write_bytes(_PNG)
    html = _make_draft("[짤방: nope]").to_html({"m1": meme})
    assert '<div class="meme-placeholder">' in html
    assert '<img class="meme"' not in html


def test_to_html_jpeg_mime(tmp_path: Path) -> None:
    img = tmp_path / "a.jpg"
    img.write_bytes(_PNG)
    html = _make_draft(f"[사진: {img}]").to_html()
    assert "data:image/jpeg;base64," in html


def test_to_html_no_arg_keeps_placeholders_backcompat() -> None:
    html = _make_draft("[사진: /x/a.jpg]\n[짤방: meme_smile]").to_html()
    assert '<div class="photo-placeholder">' in html
    assert '<div class="meme-placeholder">' in html


# --- Cycle 12: image resize before embedding ---


def _jpeg_bytes(width: int, height: int) -> bytes:
    # A gradient (not a flat color) so the encoded size is non-trivial.
    base = Image.linear_gradient("L").convert("RGB")
    img = base.resize((width, height))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _animated_gif_bytes() -> bytes:
    frames = [Image.new("P", (12, 12), color=c) for c in (1, 2, 3)]
    buf = io.BytesIO()
    frames[0].save(
        buf, "GIF", save_all=True, append_images=frames[1:], loop=0, duration=80
    )
    return buf.getvalue()


def _embedded_bytes(html: str, css_class: str) -> bytes:
    m = re.search(rf'<img class="{css_class}" src="data:[^;]+;base64,([^"]+)"', html)
    assert m is not None, f"no <img class={css_class}> data URI in html"
    return base64.b64decode(m.group(1))


def test_resize_shrinks_large_photo(tmp_path: Path) -> None:
    raw = _jpeg_bytes(3000, 2000)
    img = tmp_path / "big.jpg"
    img.write_bytes(raw)
    html = _make_draft(f"[사진: {img}]").to_html()
    embedded = _embedded_bytes(html, "photo")
    assert len(embedded) < len(raw)
    with Image.open(io.BytesIO(embedded)) as out:
        assert max(out.size) <= 1280


def test_resize_does_not_upscale_small_image(tmp_path: Path) -> None:
    raw = _jpeg_bytes(100, 80)  # already within the 1280 cap
    img = tmp_path / "small.jpg"
    img.write_bytes(raw)
    html = _make_draft(f"[사진: {img}]").to_html()
    # within cap + no rotation -> original bytes kept, no upscale
    assert _embedded_bytes(html, "photo") == raw


def test_resize_applies_exif_orientation(tmp_path: Path) -> None:
    # Landscape 1600x80 stored with orientation=6 -> portrait after transpose.
    exif = Image.Exif()
    exif[_EXIF_ORIENTATION_TAG] = 6
    base = Image.linear_gradient("L").convert("RGB").resize((1600, 80))
    img = tmp_path / "rot.jpg"
    base.save(img, "JPEG", quality=90, exif=exif)
    html = _make_draft(f"[사진: {img}]").to_html()
    embedded = _embedded_bytes(html, "photo")
    with Image.open(io.BytesIO(embedded)) as out:
        assert out.height > out.width  # orientation baked in -> now portrait
        assert max(out.size) <= 1280


def test_resize_falls_back_when_pillow_absent(tmp_path: Path, monkeypatch) -> None:
    raw = _jpeg_bytes(3000, 2000)
    img = tmp_path / "big.jpg"
    img.write_bytes(raw)
    # Simulate Pillow not installed: import inside _resize_image_bytes raises.
    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.setitem(sys.modules, "PIL.Image", None)
    monkeypatch.setitem(sys.modules, "PIL.ImageOps", None)
    html = _make_draft(f"[사진: {img}]").to_html()
    assert '<img class="photo"' in html  # no crash
    assert _embedded_bytes(html, "photo") == raw  # raw bytes embedded (fallback)


def test_resize_preserves_animated_gif_meme(tmp_path: Path) -> None:
    raw = _animated_gif_bytes()
    meme = tmp_path / "anim.gif"
    meme.write_bytes(raw)
    html = _make_draft("[짤방: g1]").to_html({"g1": meme})
    assert "data:image/gif;base64," in html
    assert _embedded_bytes(html, "meme") == raw  # frames preserved (passthrough)
