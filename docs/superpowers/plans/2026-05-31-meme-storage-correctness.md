**Status:** completed
**RPI-Cycle:** 10
**Started:** 2026-05-31

# Meme Storage Correctness — Implementation Plan

**Goal:** meme-add가 이미지를 `assets/memes/`로 복사하고, meme-build 카운트를 정확히 보고하며, tag_meme_image가 코드펜스 JSON을 허용한다.

**Architecture:** `meme_library/service.py`(순수 함수 2개 추가) + `cli.py`(meme-add 복사, meme-build 카운트)만 변경. vision 호출·본문 파서 불변.

**Tech Stack:** Python 3.11+, Typer, pytest, ruff.

---

## Task 1: service.py — ensure_in_memes_dir + JSON 추출

**Files:**
- Modify: `src/naver_blog_bot/meme_library/service.py`
- Test: `tests/unit/test_style_and_memes.py`

- [x] **Step 1: 실패 테스트 추가**

`tests/unit/test_style_and_memes.py`에 추가:

```python
def test_ensure_in_memes_dir_copies_outside_file(tmp_path) -> None:
    from naver_blog_bot.meme_library.service import ensure_in_memes_dir

    memes = tmp_path / "memes"
    src = tmp_path / "src" / "happy.png"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"img")

    dest = ensure_in_memes_dir(src, memes)
    assert dest == memes / "happy.png"
    assert dest.read_bytes() == b"img"
    assert src.exists()  # original kept


def test_ensure_in_memes_dir_keeps_file_already_inside(tmp_path) -> None:
    from naver_blog_bot.meme_library.service import ensure_in_memes_dir

    memes = tmp_path / "memes"
    memes.mkdir()
    f = memes / "inside.png"
    f.write_bytes(b"x")

    dest = ensure_in_memes_dir(f, memes)
    assert dest == f


def test_ensure_in_memes_dir_suffixes_on_name_clash(tmp_path) -> None:
    from naver_blog_bot.meme_library.service import ensure_in_memes_dir

    memes = tmp_path / "memes"
    memes.mkdir()
    (memes / "dup.png").write_bytes(b"existing")
    src = tmp_path / "dup.png"
    src.write_bytes(b"new")

    dest = ensure_in_memes_dir(src, memes)
    assert dest == memes / "dup-2.png"
    assert dest.read_bytes() == b"new"


def test_extract_meme_json_handles_code_fence() -> None:
    from naver_blog_bot.meme_library.service import _extract_meme_json

    raw = '```json\n{"tags": ["기쁨"], "use_cases": ["마무리"], "alt_text": "웃음"}\n```'
    data = _extract_meme_json(raw)
    assert data["tags"] == ["기쁨"]


def test_extract_meme_json_handles_surrounding_prose() -> None:
    from naver_blog_bot.meme_library.service import _extract_meme_json

    raw = '다음은 메타데이터입니다:\n{"tags": ["놀람"], "use_cases": ["반전"], "alt_text": "놀란 표정"}\n참고하세요.'
    data = _extract_meme_json(raw)
    assert data["tags"] == ["놀람"]


def test_extract_meme_json_raises_on_garbage() -> None:
    import pytest

    from naver_blog_bot.meme_library.service import _extract_meme_json

    with pytest.raises(ValueError, match="invalid JSON"):
        _extract_meme_json("이건 JSON이 전혀 아님")
```

- [x] **Step 2: 실패 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_style_and_memes.py -k "ensure_in_memes_dir or extract_meme_json" -q 2>&1 | tail -15
```
Expected: FAIL (함수 없음).

- [x] **Step 3: service.py 구현**

`src/naver_blog_bot/meme_library/service.py` 상단 import에 추가:
```python
import shutil
```

`tag_meme_image` 위에 두 함수 추가:
```python
def ensure_in_memes_dir(image_path: Path, memes_dir: Path) -> Path:
    memes_dir.mkdir(parents=True, exist_ok=True)
    if image_path.parent.resolve() == memes_dir.resolve():
        return image_path
    dest = memes_dir / image_path.name
    counter = 2
    while dest.exists():
        dest = memes_dir / f"{image_path.stem}-{counter}{image_path.suffix}"
        counter += 1
    shutil.copy2(image_path, dest)
    return dest


def _extract_meme_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # drop opening fence line (``` or ```json) and trailing fence
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Vision client returned invalid JSON: {raw[:100]}"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"Vision client returned invalid JSON: {raw[:100]}")
    return data
```

`tag_meme_image`에서 `json.loads` 블록을 `_extract_meme_json` 호출로 교체:
```python
def tag_meme_image(image_path: Path, vision_client: Any) -> MemeAsset:
    raw = vision_client.complete_vision(image_path=image_path, prompt=_VISION_PROMPT)
    data = _extract_meme_json(raw)
    return MemeAsset(
        id=image_path.stem,
        path=image_path,
        tags=data.get("tags", []),
        use_cases=data.get("use_cases", []),
        alt_text=data.get("alt_text", ""),
    )
```

- [x] **Step 4: 통과 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_style_and_memes.py -q 2>&1 | tail -6
```
Expected: PASS.

- [x] **Step 5: 커밋**

```bash
cd /home/indietogo/projects/naver-blog-bot && git add src/naver_blog_bot/meme_library/service.py tests/unit/test_style_and_memes.py && git commit -m "feat: add ensure_in_memes_dir and tolerant JSON extraction for meme tagging"
```

---

## Task 2: cli.py — meme-add 복사 + meme-build 카운트

**Files:**
- Modify: `src/naver_blog_bot/cli.py`
- Test: `tests/unit/test_cli.py`

- [x] **Step 1: meme-add 복사 테스트 추가**

`tests/unit/test_cli.py`에 추가 (기존 meme-fetch 테스트의 configure_paths / FakeTagger 패턴 참고):

```python
def test_meme_add_copies_into_memes_dir(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    from naver_blog_bot.config import Settings, ensure_local_directories

    settings = Settings()
    ensure_local_directories(settings)

    src = tmp_path / "outside" / "happy.png"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    class FakeTagger:
        def complete_vision(self, *, image_path, prompt):
            # asserts meme-add tags the COPIED path, not the original
            assert str(image_path).startswith(str(settings.memes_dir))
            return '{"tags": ["기쁨"], "use_cases": ["마무리"], "alt_text": "웃음"}'

    monkeypatch.setattr(cli, "build_text_completer", lambda s: FakeTagger())

    result = runner.invoke(cli.app, ["meme-add", str(src)])
    assert result.exit_code == 0, result.stdout

    copied = settings.memes_dir / "happy.png"
    assert copied.exists()

    from naver_blog_bot.meme_library.service import load_meme_index

    index = load_meme_index(settings.meme_index_path)
    assert len(index.memes) == 1
    assert str(index.memes[0].path).startswith(str(settings.memes_dir))
```

- [x] **Step 2: 실패 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_cli.py::test_meme_add_copies_into_memes_dir -q 2>&1 | tail -15
```
Expected: FAIL (현재는 원본 경로로 태깅).

- [x] **Step 3: meme_add_command 복사 추가**

`src/naver_blog_bot/cli.py`의 import에 `ensure_in_memes_dir` 추가:
```python
from naver_blog_bot.meme_library.service import (
    add_or_update_meme,
    ensure_in_memes_dir,
    load_meme_index,
    save_meme_index,
    tag_meme_image,
)
```

`meme_add_command`를 아래로 교체:
```python
@app.command("meme-add")
def meme_add_command(
    image_path: Annotated[Path, typer.Argument(help="Path to meme image file.")],
) -> None:
    if not image_path.is_file():
        typer.echo(f"Error: file not found: {image_path}")
        raise typer.Exit(1)
    settings = get_settings()
    ensure_local_directories(settings)
    dest = ensure_in_memes_dir(image_path, settings.memes_dir)
    try:
        asset = tag_meme_image(dest, build_text_completer(settings))
    except (ClaudeBackendError, ValueError) as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)
    index = load_meme_index(settings.meme_index_path)
    updated = add_or_update_meme(index, asset)
    save_meme_index(settings.meme_index_path, updated)
    typer.echo(f"Added: {dest.name} (tags: {', '.join(asset.tags)})")
```

- [x] **Step 4: meme_build_command 카운트 정확화**

`meme_build_command`를 아래로 교체:
```python
@app.command("meme-build")
def meme_build_command() -> None:
    settings = get_settings()
    ensure_local_directories(settings)
    index = load_meme_index(settings.meme_index_path)
    existing_ids = {m.id for m in index.memes}
    extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    new_count = 0
    skipped = 0
    for image_path in sorted(settings.memes_dir.iterdir()):
        if image_path.suffix.lower() not in extensions:
            continue
        if image_path.stem in existing_ids:
            skipped += 1
            continue
        try:
            asset = tag_meme_image(image_path, build_text_completer(settings))
            index = add_or_update_meme(index, asset)
            new_count += 1
            typer.echo(f"Tagged: {image_path.name}")
        except (ClaudeBackendError, ValueError) as exc:
            typer.echo(f"Skipped {image_path.name}: {exc}")
    save_meme_index(settings.meme_index_path, index)
    typer.echo(f"Done: {new_count} new image(s) tagged, {skipped} already indexed.")
```

- [x] **Step 5: 통과 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_cli.py -q 2>&1 | tail -6
```
Expected: PASS.

- [x] **Step 6: 전체 테스트 + ruff**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/ -q 2>&1 | tail -3 && uv run ruff check src/ tests/
```
Expected: ALL PASS + clean.

- [x] **Step 7: 커밋**

```bash
cd /home/indietogo/projects/naver-blog-bot && git add src/naver_blog_bot/cli.py tests/unit/test_cli.py && git commit -m "fix: meme-add copies image into assets/memes and meme-build reports accurate counts"
```

---

## Task 3: 검증 + 실제 스모크 (4개 명령)

**Files:** verify only

- [x] **Step 1: 품질 게이트**

```bash
cd /home/indietogo/projects/naver-blog-bot && bash scripts/check.sh
```
Expected: exit 0.

- [x] **Step 2: stale 인덱스/드래프트 정리 후 meme-add 재실행**

```bash
cd /home/indietogo/projects/naver-blog-bot && rm -f config/meme_index.json && uv run naver-bot meme-add sim/meme_smile.png && uv run naver-bot meme-add sim/meme_surprise.png && ls assets/memes/ && uv run python3 -c "import json; d=json.load(open('config/meme_index.json')); [print(m['id'],'->',m['path']) for m in d['memes']]"
```
Expected: `assets/memes/`에 두 PNG 존재, 인덱스 path가 `assets/memes/` 가리킴.

- [x] **Step 3: meme-build (이미 인덱스됨 → 정확한 skip 카운트)**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run naver-bot meme-build
```
Expected: `Done: 0 new image(s) tagged, 2 already indexed.`

- [x] **Step 4: meme-build 신규 파일 (새 stem)**

```bash
cd /home/indietogo/projects/naver-blog-bot && cp sim/meme_smile.png assets/memes/meme_test.png && uv run naver-bot meme-build
```
Expected: `Tagged: meme_test.png` + `Done: 1 new image(s) tagged, 2 already indexed.`

- [x] **Step 5: love 프로필 draft (food와 문체 차이 확인)**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run naver-bot draft sim/photos/cafe1.jpg sim/photos/cafe2.jpg "오늘 남자친구랑 부천 새 카페 데이트. 통창에 햇살 좋고 아메리카노 진하고 크루아상 겉바속촉이라 둘 다 행복했음" --profile love
```
Expected: 초안 생성. food 초안과 톤/구조가 다름(love는 인사말·일기체·ㅋㅋ).

- [x] **Step 6: meme-fetch (선택, 외부 URL — 사용자 동의 시)**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run naver-bot meme-fetch "<small-jpg-url>"
```
Expected: 신규 stem으로 `assets/memes/`에 다운로드 + 태깅 등록.

- [x] **Step 7: 명시 요청 없이는 추가 커밋 금지**

---

## Self-Review

- Spec 커버리지: 복사(Task1·2) / JSON 허용(Task1) / 카운트(Task2) / 실제 검증(Task3).
- Placeholder 없음 (Step 6의 `<small-jpg-url>`은 사용자 입력 자리).
- 타입 일관성: `ensure_in_memes_dir(image_path, memes_dir)`, `_extract_meme_json(raw)` Task1 정의 → cli/tag에서 사용.
- 범위: service.py + cli.py + 테스트만.
