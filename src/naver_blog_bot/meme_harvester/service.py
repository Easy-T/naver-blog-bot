import json
from pathlib import Path
from typing import Any

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
