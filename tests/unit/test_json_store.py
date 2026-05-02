from pathlib import Path

from naver_blog_bot.storage.json_store import read_json, write_json


def test_write_json_creates_parent_and_preserves_korean_text(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "payload.json"

    write_json(path, {"memo": "포포몬 체험단 후기", "count": 2})

    assert path.exists()
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert read_json(path) == {"memo": "포포몬 체험단 후기", "count": 2}
