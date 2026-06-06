import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from naver_blog_bot.photo_describer.models import PhotoCaption
from naver_blog_bot.shared.protocols import VisionCompleter
from naver_blog_bot.storage.json_store import read_json, write_json

_CATEGORIES = ["외관", "내부", "제품", "원단", "상담", "측정", "인물", "기타"]
_MAX_DIM = 1024

VISION_PROMPT = (
    "이 사진을 한국어로 분석해 JSON만 반환해라.\n"
    '형식: {"caption": "...", "category": "..."}\n'
    "caption: 사진에 실제로 보이는 것을 1-2문장으로. 간판·화면 등 글자가 보이면 포함.\n"
    "category: 다음 중 하나 — 외관, 내부, 제품, 원단, 상담, 측정, 인물, 기타.\n"
    "JSON 외 텍스트는 절대 반환하지 마라."
)


def _parse_caption(path: Path, raw: str) -> PhotoCaption:
    text = (raw or "").strip()
    caption = text
    category = "기타"
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            caption = str(data.get("caption", "")).strip()
            category = str(data.get("category", "기타")).strip()
    except json.JSONDecodeError:
        pass
    if category not in _CATEGORIES:
        category = "기타"
    return PhotoCaption(path=path, caption=caption, category=category)


def _prepare_image(path: Path, work_dir: Path) -> Path:
    """EXIF-orient + downscale into work_dir; return original path on any failure."""
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as im:
            oriented = ImageOps.exif_transpose(im)
            if max(oriented.size) > _MAX_DIM:
                oriented.thumbnail((_MAX_DIM, _MAX_DIM))
            rgb = oriented if oriented.mode == "RGB" else oriented.convert("RGB")
            work_dir.mkdir(parents=True, exist_ok=True)
            out = work_dir / f"{path.stem}.prep.jpg"
            rgb.save(out, "JPEG", quality=85)
            return out
    except Exception:
        return path


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe_photos(
    paths: Sequence[Path],
    vision_client: VisionCompleter,
    *,
    cache_path: Path | None = None,
    work_dir: Path | None = None,
) -> list[PhotoCaption]:
    cache: dict = {}
    if cache_path is not None and cache_path.exists():
        try:
            cache = read_json(cache_path)
        except Exception:
            cache = {}
    if work_dir is None:
        base = cache_path.parent if cache_path is not None else Path(".")
        work_dir = base / ".caption-tmp"

    results: list[PhotoCaption] = []
    dirty = False
    for path in paths:
        try:
            key = _file_hash(path)
        except OSError:
            results.append(PhotoCaption(path=path))
            continue
        if key in cache:
            entry = cache[key]
            results.append(
                PhotoCaption(
                    path=path,
                    caption=entry.get("caption", ""),
                    category=entry.get("category", "기타"),
                )
            )
            continue
        prepared = _prepare_image(path, work_dir)
        try:
            raw = vision_client.complete_vision(
                image_path=prepared, prompt=VISION_PROMPT
            )
            cap = _parse_caption(path, raw)
        except Exception:
            cap = PhotoCaption(path=path)
        results.append(cap)
        cache[key] = {"caption": cap.caption, "category": cap.category}
        dirty = True

    if cache_path is not None and dirty:
        write_json(cache_path, cache)
    return results
