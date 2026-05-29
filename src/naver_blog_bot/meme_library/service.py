import json
from pathlib import Path
from typing import Any

from naver_blog_bot.meme_library.models import MemeAsset, MemeIndex
from naver_blog_bot.storage.json_store import read_json, write_json

_VISION_PROMPT = """이 이미지에 어울리는 한국어 블로그 짤방 메타데이터를 JSON으로 반환해라.
JSON 외 다른 텍스트는 반환하지 마라.
{
  "tags": ["감정/분위기를 나타내는 한국어 키워드 3-6개"],
  "use_cases": ["이 짤방을 쓰기 좋은 상황 2-4개"],
  "alt_text": "이미지를 한 줄로 설명"
}"""


def load_meme_index(path: Path) -> MemeIndex:
    if not path.exists():
        return MemeIndex()
    return MemeIndex.model_validate(read_json(path))


def save_meme_index(path: Path, index: MemeIndex) -> None:
    write_json(path, index.model_dump(mode="json"))


def tag_meme_image(image_path: Path, vision_client: Any) -> MemeAsset:
    raw = vision_client.complete_vision(image_path=image_path, prompt=_VISION_PROMPT)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Vision client returned invalid JSON: {raw[:100]}") from exc
    return MemeAsset(
        id=image_path.stem,
        path=image_path,
        tags=data.get("tags", []),
        use_cases=data.get("use_cases", []),
        alt_text=data.get("alt_text", ""),
    )


def add_or_update_meme(index: MemeIndex, asset: MemeAsset) -> MemeIndex:
    memes = [m for m in index.memes if m.id != asset.id]
    memes.append(asset)
    return MemeIndex(memes=memes)
