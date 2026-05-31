# Meme Storage Correctness — Design Spec

Created: 2026-05-31
Project: naver-blog-bot
RPI-Cycle: 10

## 1. Problem

실제 스모크(cycle 9) + workflow 코드 감사로 짤방 관리에 3개 버그 확정:

1. **meme-add가 이미지를 `assets/memes/`로 복사하지 않음.** `tag_meme_image`가 `path=image_path`(원본 경로)로 `MemeAsset`을 만든다. `meme-add sim/meme_smile.png` 실행 시 인덱스에 `path=sim/meme_smile.png`가 저장되고, 파일은 `assets/memes/`로 이동/복사되지 않는다. 설계 의도(domain-glossary: "이미지를 `assets/memes/`에 저장")와 불일치. (meme-fetch는 이미 memes_dir에 다운로드하므로 OK.)

2. **meme-build의 skip 카운트가 `len(index)` 하드코딩.** `assets/memes/`가 비어 있어 0개를 스캔해도 "N existing skipped"를 출력 → 운영자가 "N개 빌드됨"으로 오해.

3. **`tag_meme_image`가 strict `json.loads`.** Vision 모델이 ```json 코드펜스나 앞뒤 설명을 붙이면 즉시 ValueError(meme-fetch는 dest.unlink까지). cycle 8과 동일한 취약성 — 방어 필요.

## 2. Goal

1. `meme-add <file>`이 이미지를 `assets/memes/`로 복사하고, 인덱스 path가 `assets/memes/<name>`을 가리킨다. 이미 memes_dir 안의 파일이면 복사 생략(멱등).
2. `meme-build`가 실제로 스캔·skip한 파일 수를 정확히 보고한다.
3. `tag_meme_image`가 코드펜스/앞뒤 설명이 섞인 응답에서도 JSON 객체를 추출한다.
4. SDK·CLI vision 경로, 본문 파서 불변.

## 3. Approach

### 3.1 memes_dir 복사 (service.py)

신규 순수 함수 `ensure_in_memes_dir(image_path: Path, memes_dir: Path) -> Path`:
- `image_path`의 부모가 이미 `memes_dir`면 그대로 반환.
- 아니면 `memes_dir/<image_path.name>`로 복사(`shutil.copy2`), 충돌 시 `<stem>-2<suffix>` 등 suffix. 복사된 경로 반환.
- memes_dir 없으면 생성.

`meme_add_command`(cli.py): `dest = ensure_in_memes_dir(image_path, settings.memes_dir)` 후 `tag_meme_image(dest, ...)`.

### 3.2 JSON 추출 허용 (service.py)

`tag_meme_image`에서 `json.loads(raw)` 대신 `_extract_meme_json(raw)`:
- ```json ... ``` 펜스 제거, 첫 `{`부터 마지막 `}`까지 슬라이스 후 `json.loads`.
- 실패 시 기존처럼 `ValueError(f"Vision client returned invalid JSON: {raw[:100]}")`.

### 3.3 meme-build 카운트 (cli.py)

`skipped` 변수를 루프에서 실제 skip한 파일 수로 집계. 메시지: `"Done: {new} new image(s) tagged, {skipped} already indexed, {failed} failed."` (failed는 선택 — 최소 new/skipped 정확화).

## 4. Out of Scope

- meme-build의 skip-by-stem 로직 자체(디렉터리 무시)는 유지 — 모든 짤방이 memes_dir에 모이면 stem 비교로 충분.
- SDK/CLI vision 호출 경로, 본문 파서, draft 로직.
- 기존 stale 인덱스(sim/ 경로) 마이그레이션 코드 — 로컬 state라 수동 재생성(인덱스 삭제 후 meme-add 재실행)으로 해결.

## 5. Files

| 파일 | 변경 |
|------|------|
| `src/naver_blog_bot/meme_library/service.py` | `ensure_in_memes_dir()` 신규, `_extract_meme_json()` 신규, `tag_meme_image` JSON 추출 사용 |
| `src/naver_blog_bot/cli.py` | `meme_add_command` 복사 단계 추가, `meme_build_command` 카운트 정확화 |
| `tests/unit/test_style_and_memes.py` | ensure_in_memes_dir·_extract_meme_json 단위 테스트 |
| `tests/unit/test_cli.py` | meme-add 복사 동작 테스트(기존 meme-fetch 패턴 재사용) |

## 6. Success Criteria

- `ensure_in_memes_dir`: memes_dir 밖 파일은 복사, 안의 파일은 그대로; 충돌 suffix (단위 테스트).
- `_extract_meme_json`: 코드펜스/앞뒤 설명 섞인 입력에서 dict 추출 (단위 테스트).
- `meme-add` 후 파일이 `assets/memes/`에 존재 + 인덱스 path가 memes_dir 가리킴 (CLI 테스트).
- 전체 테스트 그린 + ruff.
- (수동) `meme-add sim/meme_smile.png` → `assets/memes/meme_smile.png` 생성, 인덱스 path 정확. `meme-build` → 정확한 카운트. `meme-fetch <URL>` → 신규 stem 등록.

## 7. Self-Review

- Placeholder 없음. 범위: service.py + cli.py + 테스트.
- 시그니처: `tag_meme_image(image_path, vision_client)` 불변(내부만). `ensure_in_memes_dir`·`_extract_meme_json` 신규.
- 오프라인 테스트 유지.
