# 설계: 사진 인식형 초안 생성 (Photo-Aware Draft Generation)

- 작성일: 2026-06-07
- 상태: 승인됨 (브레인스토밍 완료, default vision ON)
- 관련: `post_generator/generator.py`, `shared/claude_client.py`, `cli.py`

## 배경 / 문제

현재 `PostGenerator.generate`는 사진을 **분석하지 않는다**. `complete_text`만 호출하고 사진은 *파일 경로 문자열*로만 프롬프트에 들어간다. 본문은 100% 메모에서만 생성되고, `[사진: NN.jpg]` 자리표시는 사진 내용과 무관하게 순서대로 균등 배치된다. 결과적으로 사진과 글이 따로 논다(실측: 뮤토테일러 초안에서 측정 사진 옆에 매장 외관 설명이 붙는 등).

## 목표 / 성공 기준 (goal-driven — 충족할 때까지 반복)

1. vision ON 기본 상태로 `draft` 실행 시, 생성된 본문에서 각 `[사진: path]`가 **그 사진의 실제 내용을 서술한 텍스트와 인접**한다 (외관 사진 옆 외관 설명, 측정 사진 옆 측정 설명).
2. 사진을 **이야기 흐름**(외관→입장→내부→제품→상담→착장→총평)에 맞게 재배치하고 유사컷은 묶는다.
3. `--no-vision` 플래그로 **기존 동작(경로-only)** 을 그대로 재현한다.
4. **캡션 캐시**: 동일 사진 재실행 시 vision 호출 0회.
5. EXIF로 회전된 사진도 올바르게 묘사된다.
6. 기존 테스트 전부 통과 + 신규 단위 테스트 통과.

## 비목표 (YAGNI)

- 사진 자동 보정/리터칭, 워터마크 제거 등 이미지 편집.
- 사진 클러스터링 알고리즘(유사컷 묶기는 LLM이 캡션 기반으로 처리; 별도 비전 임베딩 X).
- 멀티 블로그/멀티 프로필 동시 처리.

## 설계 (접근법 A: 캡션 → 작성 2단계)

### 1) 신규 모듈 `photo_describer`
기존 `style_profiler`·`meme_library`와 같은 작은 단위.

- 모델 `PhotoCaption`: `path: Path`, `caption: str`(한국어 1–2문장), `category: str`(외관/내부/제품/원단/상담/측정/인물/기타).
- `describe_photos(paths, completer, *, cache_path) -> list[PhotoCaption]`
  - 각 사진을 **EXIF 자동 회전 + 다운스케일(~1024px, 재인코딩)** 후 vision 호출.
  - 백엔드별 배치/청크 (sdk: 멀티 이미지 블록 / claude-code: 적정 청크). 1차 구현은 안전하게 사진별 호출 + 캐시로 비용 상쇄, 배치는 후속 최적화 여지로 남김.
  - 반환은 입력 순서 유지(배치/그룹핑은 작성 단계에서).
- **캡션 캐시**: 파일 content-hash(SHA-256) 키 사이드카 JSON(`drafts/.caption-cache.json` 또는 설정 경로). 히트 시 vision 생략.

### 2) `shared/claude_client.py`
- `complete_vision`은 단일 이미지 기준 유지(이미 존재). 필요 시 EXIF/리사이즈는 `photo_describer`에서 전처리한 임시 바이트/파일로 호출(클라이언트는 순수 유지).

### 3) `PostGenerator.generate`
- 시그니처에 `use_vision: bool = True` 추가.
- vision ON: `describe_photos`로 캡션 확보 → `_build_user_prompt`에 **"사진 목록(경로 + 내용 + 카테고리)"** 주입.
- SYSTEM_PROMPT 보강: "주어진 사진 설명에 근거해 서술하라. 사진을 내용 흐름에 맞게 **재배치·그룹핑**하라. 설명에 없는 내용을 지어내지 마라. 각 사진은 `[사진: path]`로 적절한 위치에 배치."
- vision OFF: 기존 경로-only 동작.
- 짤방 배치 단계(`_place_memes_in_draft`)는 변경 없음.

### 4) CLI
- `draft`에 `--no-vision` 플래그(기본 vision ON). `generate(use_vision=...)`로 전달.

## 데이터 흐름

```
photos
  → [EXIF 보정 + 리사이즈]            (photo_describer 전처리)
  → vision 캡션 (캐시 조회/저장)       (describe_photos)
  → captions(path+내용+카테고리)
  → compose: complete_text(캡션 + style_profile + memo + examples + memes)
  → [사진/이모티콘/짤방] 마커 본문
  → 짤방 배치(_place_memes_in_draft)
  → Draft(저장)
```

## 에러 처리

- vision 실패/타임아웃 → 해당 사진 캡션 빈 문자열로 두고 진행(전체 실패 방지). 모든 사진 실패 시 경로-only로 폴백.
- 캐시 파일 손상/파싱 실패 → 무시하고 재생성(예외 전파 금지).
- 이미지 디코드 실패(Pillow 없음/지원 안 함) → 원본 그대로 vision 시도, 안 되면 캡션 빈값.

## 테스트 전략

- `describe_photos`: 목 completer로 (a) 캡션 파싱, (b) 캐시 히트 시 호출 0회, (c) EXIF 회전 입력 전처리, (d) vision 예외 시 빈 캡션 폴백.
- `PostGenerator.generate(use_vision=True)`: 목 completer로 캡션이 user_prompt에 포함되는지; `use_vision=False` 폴백이 기존과 동일한지.
- 회귀: 기존 post_generator/cli 테스트 통과.

## 아키텍처 영향 (ADR 필요)

- 신규 모듈 `photo_describer` 추가 + `generate` 데이터 흐름 변경(텍스트-only → vision 선행) → **ADR-010** 작성 대상(§5). 구현/클로즈아웃 단계에서 `docs/ai-context/architecture.md`에 append.
- `CLAUDE.md` Modules 섹션에 `photo_describer` 한 줄 추가(세션 종료 직전).

## 미해결/구현 시 결정

- 배치 vs 사진별 호출의 최종 청크 크기 — 구현 중 실제 latency 측정 후 결정(1차는 사진별 + 캐시).
- 캐시 위치/이름 — `drafts/.caption-cache.json` 제안(gitignore 하위).
