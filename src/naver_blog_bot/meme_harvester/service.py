import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from naver_blog_bot.blog_scraper.models import ImageBlock, PostDocument
from naver_blog_bot.meme_harvester.models import HarvestResult
from naver_blog_bot.meme_library.models import MemeAsset
from naver_blog_bot.storage.json_store import read_json, write_json

CLASSIFY_PROMPT_HEAD = (
    "이 이미지가 블로그 '짤방'(반응용 밈/움짤/스크린샷/일러스트)인지, "
    "아니면 글의 콘텐츠를 보여주는 실제 촬영 사진인지 한국어로 판단해라.\n"
    "실제 풍경·인물·제품·음식·매장 등을 직접 찍은 사진이면 is_meme=false. "
    "반응을 표현하려고 가져다 쓴 밈/움짤/캡처/그림이면 is_meme=true.\n"
    'JSON만 반환: {"is_meme": true/false, "tags": [...], '
    '"use_cases": [...], "alt_text": "..."}\n'
    "tags: 감정/분위기 키워드 3-6개. use_cases: 이 짤방을 쓰기 좋은 상황 2-4개. "
    "alt_text: 한 줄 설명. JSON 외 텍스트 금지."
)


def _extract_json(raw: str) -> dict[str, Any]:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("not a dict")
    return data


def _parse_classification(raw: str) -> dict[str, Any]:
    try:
        data = _extract_json(raw)
    except (json.JSONDecodeError, ValueError):
        return {"is_meme": False, "tags": [], "use_cases": [], "alt_text": ""}
    return {
        "is_meme": bool(data.get("is_meme", False)),
        "tags": list(data.get("tags", []) or []),
        "use_cases": list(data.get("use_cases", []) or []),
        "alt_text": str(data.get("alt_text", "") or ""),
    }


def classify_image(
    image_path: Path, vision_client: Any, *, context: str = ""
) -> dict[str, Any]:
    prompt = CLASSIFY_PROMPT_HEAD
    if context.strip():
        prompt += f"\n\n이 이미지가 사용된 문맥(참고): {context.strip()[:300]}"
    raw = vision_client.complete_vision(image_path=image_path, prompt=prompt)
    return _parse_classification(raw)


FetchFn = Callable[..., "bytes | None"]

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _default_fetch(url: str, *, referer: str) -> bytes | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": referer or "https://m.blog.naver.com/",
    }
    try:
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


def _image_contexts(document: PostDocument) -> list[tuple[str, str]]:
    """Return (src, surrounding_text) for each ImageBlock that has a src."""
    blocks = document.blocks
    out: list[tuple[str, str]] = []
    for i, block in enumerate(blocks):
        if isinstance(block, ImageBlock) and block.src:
            before = ""
            after = ""
            for j in range(i - 1, -1, -1):
                if getattr(blocks[j], "type", "") == "text":
                    before = blocks[j].content
                    break
            for j in range(i + 1, len(blocks)):
                if getattr(blocks[j], "type", "") == "text":
                    after = blocks[j].content
                    break
            out.append((block.src, f"{before} {after}".strip()))
    return out


def _ext_for(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in _IMG_EXTS else ".jpg"


def _hash_in_cache(cache: dict[str, Any], digest: str) -> bool:
    return any(v.get("hash") == digest for v in cache.values())


def _meta_for_hash(
    cache: dict[str, Any], digest: str, assets_by_hash: dict[str, MemeAsset]
) -> dict[str, Any]:
    if digest in assets_by_hash:
        a = assets_by_hash[digest]
        return {
            "is_meme": True,
            "tags": a.tags,
            "use_cases": a.use_cases,
            "alt_text": a.alt_text,
            "ext": a.path.suffix,
        }
    for v in cache.values():
        if v.get("hash") == digest:
            return {
                k: v[k]
                for k in ("is_meme", "tags", "use_cases", "alt_text", "ext")
                if k in v
            }
    return {
        "is_meme": False,
        "tags": [],
        "use_cases": [],
        "alt_text": "",
        "ext": ".jpg",
    }


def harvest_memes(
    documents: Sequence[PostDocument],
    vision_client: Any,
    *,
    memes_dir: Path,
    cache_path: Path | None = None,
    fetch: FetchFn | None = None,
) -> HarvestResult:
    fetch = fetch or _default_fetch
    memes_dir.mkdir(parents=True, exist_ok=True)

    cache: dict[str, Any] = {}
    if cache_path is not None and cache_path.exists():
        try:
            cache = read_json(cache_path)
        except Exception:
            cache = {}

    assets_by_hash: dict[str, MemeAsset] = {}
    meme_srcs: list[str] = []
    dirty = False

    for document in documents:
        for src, context in _image_contexts(document):
            entry = cache.get(src)
            if entry is None:
                data = fetch(src, referer=document.url)
                if not data:
                    continue
                digest = hashlib.sha256(data).hexdigest()
                ext = _ext_for(src)
                if digest in assets_by_hash or _hash_in_cache(cache, digest):
                    meta = _meta_for_hash(cache, digest, assets_by_hash)
                else:
                    dest = memes_dir / f"harvested-{digest[:12]}{ext}"
                    dest.write_bytes(data)
                    try:
                        meta = classify_image(dest, vision_client, context=context)
                    except Exception:
                        meta = {
                            "is_meme": False,
                            "tags": [],
                            "use_cases": [],
                            "alt_text": "",
                        }
                    if not meta["is_meme"]:
                        dest.unlink(missing_ok=True)
                    meta = {**meta, "ext": ext}
                entry = {"hash": digest, **meta}
                cache[src] = entry
                dirty = True
            digest = entry["hash"]
            if not entry.get("is_meme"):
                continue
            meme_srcs.append(src)
            existing = assets_by_hash.get(digest)
            if existing is None:
                ext = entry.get("ext", ".jpg")
                assets_by_hash[digest] = MemeAsset(
                    id=f"harvested-{digest[:12]}",
                    path=memes_dir / f"harvested-{digest[:12]}{ext}",
                    tags=list(entry.get("tags", [])),
                    use_cases=list(entry.get("use_cases", [])),
                    alt_text=entry.get("alt_text", ""),
                    frequency=1,
                )
            else:
                assets_by_hash[digest] = existing.model_copy(
                    update={"frequency": existing.frequency + 1}
                )

    if cache_path is not None and dirty:
        write_json(cache_path, cache)

    return HarvestResult(assets=list(assets_by_hash.values()), meme_srcs=meme_srcs)
