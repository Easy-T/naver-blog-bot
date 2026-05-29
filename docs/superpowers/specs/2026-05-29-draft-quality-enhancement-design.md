# Draft Quality Enhancement Design Spec

Created: 2026-05-29
Project: naver-blog-bot

## 1. Goal

이번 사이클은 `publish` 없이 사용 가능한 고품질 초안 워크플로우를 완성한다.
사용자는 `draft` → `preview` → 브라우저에서 확인 → 클립보드 복사 → 네이버 SmartEditor 붙여넣기 순서로 운영한다.

성공 기준:
- `preview` 명령이 브라우저 HTML 파일을 열고 클립보드에 내용을 복사한다
- `profile-refresh` 후 `config/style_profiles/<name>-examples.json`이 생성된다
- `draft` 생성 시 few-shot 예시가 Claude 프롬프트에 주입된다
- `meme-add`, `meme-fetch`, `meme-build` 명령이 Claude Vision으로 짤방을 자동 태깅한다
- 짤방이 등록된 경우 `draft`가 초안 전체를 분석해 문단별로 짤방 마커를 삽입한다
- 캐시 오염 버그가 수정된다

## 2. Out of Scope

- `publish` 커맨드 구현 (Phase 2 이후)
- 네이버 SmartEditor 자동화
- EXIF 스트리핑 (publisher와 함께 구현)
- `claude -p` 웹서치 기반 이미지 검색

## 3. Prerequisite Bug Fixes

### 3.1 `to_cache_text()` 캐시 오염 수정

**파일:** `src/naver_blog_bot/style_profiler/models.py`, `src/naver_blog_bot/meme_library/models.py`

**문제:** `to_cache_text()`가 `updated_at` 타임스탬프를 포함하여 내용 변경 없이 재저장해도 캐시 미스 발생.

**수정:** `StyleProfile.to_cache_text()`에서 `updated_at`, `blog_url`, `profile_name` 제외.
`MemeIndex.to_cache_text()`에서 `updated_at` 제외.
안정적인 문체·짤방 콘텐츠 필드만 직렬화.

### 3.2 `TextCompleter` 프로토콜 통일

**파일:** `src/naver_blog_bot/shared/protocols.py` (신규), `src/naver_blog_bot/post_generator/generator.py`, `src/naver_blog_bot/style_profiler/refresh.py`

**문제:** `TextCompleter` 프로토콜이 `generator.py`와 `refresh.py` 양쪽에 중복 정의.

**수정:** `shared/protocols.py`에 단일 정의. 두 모듈은 임포트해서 사용.

## 4. Subsystem 1: HTML 미리보기 + 클립보드 복사

### 4.1 동작

```
naver-bot preview draft-20260529-142530
```

1. `drafts/<id>.json` 로드
2. `Draft.to_html()` 호출 → `drafts/<id>.html` 생성
3. `webbrowser.open(html_path)` 로 기본 브라우저에서 자동 열기
4. `pyperclip.copy(draft.body_markdown)` 로 클립보드에 마크다운 복사
5. 터미널: `"Preview opened: drafts/<id>.html\nContent copied to clipboard."`

WSL2 환경에서 `pyperclip`은 `xclip` 또는 `xsel` 설치 필요. 미설치 시 클립보드 복사를 건너뛰고 경고만 출력한다.

### 4.2 HTML 렌더링 규칙

- `[사진: path]` → 회색 박스 + 파일명 표시
- `{{이모티콘:감정}}` → 노란 배지로 시각화
- `[짤방: path]` → `assets/memes/`에 파일이 있으면 `<img>` 렌더링, 없으면 회색 박스
- 레이아웃: 흰 배경, 최대 너비 720px, 네이버 블로그 유사 본문 폰트(Noto Sans KR CDN)

### 4.3 파일 변경

| 파일 | 변경 |
|------|------|
| `post_generator/models.py` | `Draft.to_html()` 추가 |
| `cli.py` | `preview_command()` 갱신 |
| `pyproject.toml` | `pyperclip` 의존성 추가 |

## 5. Subsystem 2: Few-shot 예시 포스트

### 5.1 profile-refresh 저장

`profile-refresh` 실행 시 스크래핑한 포스트 중 최대 3개의 `structured_text`를
`config/style_profiles/<name>-examples.json`에 저장한다.

저장 형식:
```json
[
  {"title": "포스트 제목", "url": "https://...", "structured_text": "..."},
  ...
]
```

`--count`가 3 미만이면 그 수만큼 저장. 로컬 파일 소스만 사용한 경우 examples 파일은 생성하지 않는다.

### 5.2 draft 주입

`draft` 명령 실행 시 `<name>-examples.json`이 존재하면 로드.
`PostGenerator._build_user_prompt()`의 user prompt에 "참고 예시 포스트" 섹션으로 추가.
파일이 없으면 현재처럼 스타일 프로필만 사용 (하위 호환 유지).

예시는 **cacheable_context 블록이 아닌 user_prompt**에 주입한다 — 예시가 바뀔 때마다 캐시 무효화를 방지하기 위함.

### 5.3 파일 변경

| 파일 | 변경 |
|------|------|
| `style_profiler/examples.py` | `ExamplePost` 모델, `FewShotRepository` (신규) |
| `cli.py` | `profile_refresh_command()` — examples 저장 추가 |
| `post_generator/generator.py` | `_build_user_prompt()` — examples 주입 추가 |

## 6. Subsystem 3: Meme 관리

### 6.1 Vision 클라이언트 확장

`ClaudeCodeTextClient`에 `complete_vision(image_path, prompt)` 추가:
```
claude -p --image <path> "<prompt>" --output-format json
```

`ClaudeTextClient`는 기존 SDK image content block 방식 사용.

Vision 프롬프트 (한국어 블로그 맥락):
```
이 이미지에 어울리는 한국어 블로그 짤방 메타데이터를 JSON으로 반환해라.
{
  "tags": ["감정/분위기 키워드 3-6개"],
  "use_cases": ["언제 쓰면 좋은지 2-4개"],
  "alt_text": "한 줄 설명"
}
```

### 6.2 `meme-add <파일경로>`

```bash
naver-bot meme-add assets/memes/thumbsup.jpg
```

1. 파일 존재 확인
2. `complete_vision()` 호출 → JSON 파싱
3. `MemeAsset` 생성 → `config/meme_index.json`에 추가
4. 출력: `"Added: thumbsup.jpg (tags: 만족, 추천)"`
5. 이미 등록된 파일이면 태그 갱신 후 `"Updated: ..."` 출력

### 6.3 `meme-fetch <URL>`

```bash
naver-bot meme-fetch https://example.com/reaction.gif
```

1. `httpx`로 이미지 다운로드
2. Content-Type으로 확장자 결정, URL path로 파일명 보조 결정
3. `assets/memes/<filename>` 저장 (충돌 시 `<filename>-2` 등 suffix)
4. 이후 `meme-add`와 동일한 Vision 태깅 파이프라인

### 6.4 `meme-build`

```bash
naver-bot meme-build
```

1. `assets/memes/`를 스캔
2. `meme_index.json`에 없는 이미지만 Vision 태깅 후 추가
3. 이미 등록된 파일은 건너뜀
4. 출력: `"Processed 5 new images, skipped 12 existing."`

### 6.5 파일 변경

| 파일 | 변경 |
|------|------|
| `shared/claude_client.py` | `complete_vision()` 추가 |
| `meme_library/service.py` | `tag_meme_image()` 추가 |
| `cli.py` | `meme_add_command()`, `meme_build_command()`, `meme_fetch_command()` 추가 |
| `pyproject.toml` | `httpx` 의존성 추가 |

## 7. Subsystem 4: 문맥 기반 짤방 배치

### 7.1 2단계 Claude 호출

`PostGenerator.generate()` 에 2차 호출 추가:

**1차 호출 (기존):** 초안 본문 생성

**2차 호출 (신규):** 짤방 배치
- 조건: `meme_index.memes`가 비어있지 않을 때만 실행
- 입력: 생성된 초안 본문 + 짤방 인덱스 목록 (id, use_cases, tags)
- 출력: `[짤방: {id}]` 마커가 삽입된 초안 본문

### 7.2 2차 호출 프롬프트

```
다음 초안과 짤방 목록을 보고, 각 짤방이 자연스럽게 어울리는 문단 뒤에만
[짤방: {id}] 마커를 삽입해라.
- 억지로 넣지 마라. 정말 어울리는 곳에만.
- 마커 외 본문 텍스트는 절대 수정하지 마라.
- 짤방 하나는 한 번만 사용.
```

### 7.3 파일 변경

| 파일 | 변경 |
|------|------|
| `post_generator/generator.py` | `_place_memes_in_draft()` 메서드 추가, `generate()` 에 2차 호출 추가 |

## 8. 구현 순서 (의존성)

```
Step 0: 버그 수정 (to_cache_text, TextCompleter 통일)
Step 1: HTML 미리보기 + 클립보드 (독립)
Step 2: Few-shot 예시 저장/주입 (Step 0 완료 후)
Step 3: Vision 클라이언트 확장 (독립)
Step 4: meme-add / meme-fetch / meme-build (Step 3 완료 후)
Step 5: 문맥 기반 짤방 배치 (Step 4 완료 후)
```

## 9. 의존성 추가

| 패키지 | 용도 |
|--------|------|
| `pyperclip` | 클립보드 복사 |
| `httpx` | `meme-fetch` 이미지 다운로드 |

## 10. Self-Review

- **Placeholder 검사:** TBD/TODO 없음
- **내부 일관성:** 구현 순서가 의존성 방향과 일치. few-shot이 캐시 버그 수정 이후 배치됨
- **범위 검사:** publish, EXIF, 웹서치 자동화는 모두 명시적으로 제외됨
- **모호성 검사:** WSL2 pyperclip 조건부 처리 명시. few-shot을 user_prompt에 넣는 이유(캐시 전략) 명시
