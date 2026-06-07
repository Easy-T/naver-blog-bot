import base64
import html as _html
import io
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


_PHOTO_MAX_DIM = 1280
_MEME_MAX_DIM = 480
_JPEG_QUALITY = 82
_EXIF_ORIENTATION_TAG = 0x0112

_EMOTICON_RE = re.compile(r"\{\{이모티콘:([^}]+)\}\}")


def _emoticon_to_cue(text: str) -> str:
    """Rewrite inline {{이모티콘:유형}} markers as plain-text insertion cues."""
    return _EMOTICON_RE.sub(lambda m: f"〔😊 이모티콘: {m.group(1)}〕", text)


def _resize_image_bytes(raw: bytes, max_dim: int) -> tuple[bytes, str] | None:
    """Resize/re-encode image bytes for a lighter base64 embed.

    Returns (new_bytes, mime) when smaller, else None (caller keeps the
    original bytes). None on: Pillow missing, decode failure, genuine animated GIF/WebP,
    nothing to do (within cap and unrotated), or re-encode not smaller.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    try:
        with Image.open(io.BytesIO(raw)) as im:
            fmt = (im.format or "").upper()
            if fmt in {"GIF", "WEBP"} and getattr(im, "is_animated", False):
                return None  # genuine animated GIF/WebP: preserve frames
            if getattr(im, "n_frames", 1) > 1:
                # multi-frame still (iPhone MPO, multi-page TIFF): primary frame
                im.seek(0)
            orientation = im.getexif().get(_EXIF_ORIENTATION_TAG, 1)
            if max(im.size) <= max_dim and orientation == 1:
                return None  # nothing to do; keep original bytes + suffix mime
            oriented = ImageOps.exif_transpose(im)
            if max(oriented.size) > max_dim:
                oriented.thumbnail((max_dim, max_dim))
            out = io.BytesIO()
            if fmt == "PNG":
                oriented.save(out, "PNG", optimize=True)
                mime = "image/png"
            elif fmt == "WEBP":
                oriented.save(out, "WEBP", quality=_JPEG_QUALITY, method=6)
                mime = "image/webp"
            else:
                rgb = oriented if oriented.mode == "RGB" else oriented.convert("RGB")
                rgb.save(out, "JPEG", quality=_JPEG_QUALITY, optimize=True)
                mime = "image/jpeg"
    except Exception:
        return None
    data = out.getvalue()
    if len(data) >= len(raw):
        return None
    return data, mime


def _image_data_uri(path: Path, max_dim: int | None = None) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg")
    if max_dim is not None:
        resized = _resize_image_bytes(raw, max_dim)
        if resized is not None:
            raw, mime = resized
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"


class Draft(BaseModel):
    id: str
    title: str
    memo: str
    body_markdown: str
    photo_paths: list[Path]
    selected_memes: list[Path] = Field(default_factory=list)
    ogq_artwork_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def preview_text(self) -> str:
        photos = "\n".join(f"- {path}" for path in self.photo_paths) or "- (none)"
        memes = "\n".join(f"- {path}" for path in self.selected_memes) or "- (none)"
        ogq = self.ogq_artwork_id or "(none)"
        return (
            f"# {self.title}\n\n"
            f"Draft ID: {self.id}\n\n"
            f"Created: {self.created_at.isoformat()}\n\n"
            f"Memo: {self.memo}\n\n"
            f"Photos:\n{photos}\n\n"
            f"OGQ: {ogq}\n\n"
            f"Memes:\n{memes}\n\n"
            f"---\n\n"
            f"{self.body_markdown}\n"
        )

    def to_html(self, meme_paths: dict[str, Path] | None = None) -> str:
        meme_paths = meme_paths or {}
        lines: list[str] = []
        for line in self.body_markdown.splitlines():
            stripped = line.strip()
            if not stripped:
                lines.append("<br>")
                continue
            if stripped.startswith("[사진:"):
                path = stripped[4:-1].strip()
                uri = _image_data_uri(Path(path), _PHOTO_MAX_DIM)
                if uri:
                    lines.append(
                        f'<img class="photo" src="{uri}" alt="{_html.escape(path)}">'
                    )
                else:
                    lines.append(
                        f'<div class="photo-placeholder">📷 {_html.escape(path)}</div>'
                    )
            elif stripped.startswith("[짤방:"):
                ref = stripped[4:-1].strip()
                target = meme_paths.get(ref)
                uri = _image_data_uri(Path(target), _MEME_MAX_DIM) if target else None
                if uri:
                    lines.append(
                        f'<img class="meme" src="{uri}" alt="짤방: {_html.escape(ref)}">'
                    )
                else:
                    lines.append(
                        f'<div class="meme-placeholder">🖼️ 짤방: {_html.escape(ref)}</div>'
                    )
            elif stripped.startswith("### "):
                lines.append(f"<h3>{_html.escape(stripped[4:])}</h3>")
            elif stripped.startswith("## "):
                lines.append(f"<h2>{_html.escape(stripped[3:])}</h2>")
            elif stripped.startswith("# "):
                lines.append(f"<h1>{_html.escape(stripped[2:])}</h1>")
            else:
                processed = re.sub(
                    r"\{\{이모티콘:([^}]+)\}\}",
                    lambda m: (
                        f'<span class="emoticon-badge">😊 {_html.escape(m.group(1))}</span>'
                    ),
                    _html.escape(line),
                )
                lines.append(f"<p>{processed}</p>")

        body_html = "\n".join(lines)
        escaped_title = _html.escape(self.title)
        escaped_memo = _html.escape(self.memo)
        return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{escaped_title}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap" rel="stylesheet">
<style>
body{{font-family:'Noto Sans KR',sans-serif;background:#f5f5f5;margin:0;padding:20px}}
.post{{max-width:720px;margin:0 auto;background:#fff;padding:40px;border-radius:8px}}
.meta{{color:#888;font-size:13px;margin-bottom:20px;border-bottom:1px solid #eee;padding-bottom:16px}}
img.photo{{max-width:100%;height:auto;display:block;margin:16px auto;border-radius:6px}}
img.meme{{max-width:200px;height:auto;display:block;margin:12px auto;border-radius:6px}}
.photo-placeholder{{background:#e0e0e0;border:2px dashed #bbb;padding:30px;text-align:center;margin:16px 0;border-radius:4px;color:#666}}
.meme-placeholder{{background:#fff3e0;border:2px dashed #ffb74d;padding:20px;text-align:center;margin:16px 0;border-radius:4px;color:#e65100}}
.emoticon-badge{{background:#fff9c4;border:1px solid #f9a825;border-radius:12px;padding:2px 8px;font-size:13px}}
h1{{font-size:24px}}h2{{font-size:20px}}h3{{font-size:17px}}
p{{line-height:1.8;margin:8px 0}}
</style>
</head>
<body>
<div class="post">
<div class="meta">
  <strong>{escaped_title}</strong><br>
  Draft ID: {_html.escape(self.id)}<br>
  Created: {self.created_at.isoformat()}<br>
  Memo: {escaped_memo}
</div>
{body_html}
</div>
</body>
</html>"""

    def to_paste_text(self, meme_labels: dict[str, str] | None = None) -> str:
        """Render body markers as human-readable SmartEditor insertion cues.

        Photo/meme markers become 〔…〕 cues (basename / label only, no absolute
        paths); inline emoticon markers become 〔😊 …〕; markdown heading hashes
        are stripped; plain paragraphs and blank lines are preserved.
        `meme_labels` maps a meme id to a human label (built by the caller to
        keep this model decoupled from meme_library — ADR-007/009); an unknown
        id falls back to the raw id.
        """
        meme_labels = meme_labels or {}
        out: list[str] = []
        for line in self.body_markdown.splitlines():
            stripped = line.strip()
            if not stripped:
                out.append("")
            elif stripped.startswith("[사진:"):
                name = Path(stripped[4:-1].strip()).name
                out.append(f"〔📷 사진 삽입: {name}〕")
            elif stripped.startswith("[짤방:"):
                ref = stripped[4:-1].strip()
                out.append(f"〔🖼️ 짤방: {meme_labels.get(ref, ref)}〕")
            elif stripped.startswith("### "):
                out.append(_emoticon_to_cue(stripped[4:]))
            elif stripped.startswith("## "):
                out.append(_emoticon_to_cue(stripped[3:]))
            elif stripped.startswith("# "):
                out.append(_emoticon_to_cue(stripped[2:]))
            else:
                out.append(_emoticon_to_cue(line))
        return "\n".join(out)
