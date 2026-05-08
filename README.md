# naver-blog-bot

내 블로그 문체를 학습해서, 사진과 메모만 주면 블로그 초안을 자동으로 써주는 로컬 CLI 도구입니다.

체험단 후기, 카페 방문기, 제품 리뷰처럼 **같은 패턴이 반복되는 글**을 자주 쓰는 분께 적합합니다.

---

## 어떻게 동작하나요?

```
내 블로그 URL
      │
      ▼
 [문체 학습]  ─────────────────────────────────────────────────
      │                                                        │
      │  내 블로그 포스트를 읽어서                              │
      │  "나는 이런 식으로 글을 쓰는구나"를                     │
      │  프로필로 저장해 둡니다                                 │
      │                                                        │
      ▼                                                        │
 [초안 생성]  ◀─── 사진 경로 + 짧은 메모                       │
      │                                                        │
      │  학습한 문체 + 메모를 Claude AI에게 전달               │
      │  → 내 스타일로 쓴 블로그 초안 마크다운 반환            │
      │                                                        │
      ▼                                                        │
 [미리보기]                                                    │
      │                                                        │
      │  생성된 초안을 터미널에서 확인                          │
      │  마음에 들면 직접 블로그에 복사/붙여넣기                │
      │                                                        │
      └────────────────────────────────────────────────────────
```

한 번 문체를 학습해두면, 이후에는 **사진 + 메모 → 초안** 과정만 반복합니다.

---

## 준비물

| 항목 | 설명 |
|------|------|
| Python 3.11 이상 | [python.org](https://www.python.org/downloads/) |
| uv | Python 패키지 관리 도구 (`pip install uv`) |
| Claude Code CLI 로그인 | API 키 없이 초안을 생성하려면 필요 |
| Anthropic API 키 (선택) | SDK 백엔드를 강제로 사용할 때만 필요 |
| 네이버 블로그 (선택) | 문체 학습용. 없으면 로컬 샘플 파일로 대체 가능 |

---

## 설치

```bash
# 1. 저장소 클론
git clone https://github.com/Easy-T/naver-blog-bot.git
cd naver-blog-bot

# 2. 의존성 설치
uv sync

# 3. Playwright 브라우저 설치 (블로그 스크래핑용)
uv run playwright install chromium
```

---

## 처음 설정

### 0단계 — Claude Code 로그인 확인

API 키 없이 쓰려면 PC에 Claude Code CLI가 설치되어 있고 로그인되어 있어야 합니다.

```bash
claude
```

위 명령으로 Claude Code가 정상 실행되는지 확인하세요. `naver-bot`은 내부적으로 `claude -p --output-format json`을 호출합니다.

### 1단계 — .env 파일 만들기

프로젝트 루트에 `.env` 파일을 만들고 아래 내용을 채웁니다.

```bash
# .env

# 기본값: auto
# - auto: Claude Code CLI가 있으면 사용, 없으면 Anthropic SDK 사용
# - claude-code: Claude Code CLI만 사용
# - anthropic-sdk: Anthropic SDK만 사용
NAVER_BOT_CLAUDE_BACKEND=auto

# Claude Code CLI 명령 이름. 보통 변경하지 않아도 됩니다.
NAVER_BOT_CLAUDE_COMMAND=claude

# Anthropic SDK 백엔드를 강제로 쓸 때만 필요합니다.
# ANTHROPIC_API_KEY=sk-ant-...

# 내 블로그 주소 (profile-refresh의 기본 blog_url로 사용됨)
NAVER_BOT_BLOG_URL=https://blog.naver.com/내아이디

# OGQ 이모티콘 (사용하는 이모티콘 세트 정보, 없으면 생략 가능)
NAVER_BOT_OGQ_ARTWORK_ID=644e042a7d7f8
NAVER_BOT_OGQ_NAME=세루리안
```

### 2단계 — 로컬 디렉터리 초기화

```bash
naver-bot init
```

아래 폴더들이 자동으로 생성됩니다.

```
naver-blog-bot/
├── config/
│   └── style_profiles/   ← 학습한 문체 프로필이 저장되는 곳
├── drafts/               ← 생성된 초안이 저장되는 곳
├── assets/
│   └── memes/            ← 자주 쓰는 짤방 이미지를 여기 넣으세요
└── browser-profile/      ← 브라우저 세션 (자동 관리)
```

---

## 사용법

### Step 1 — 내 문체 학습시키기 (`profile-refresh`)

AI가 내 블로그 글을 읽고 "이 사람은 이런 식으로 쓰는구나"를 파악합니다.  
결과는 `config/style_profiles/default.json`에 저장됩니다.

**내 네이버 블로그 전체에서 최근 포스트 5개 학습:**

```bash
naver-bot profile-refresh https://blog.naver.com/내아이디
```

**특정 포스트 URL 하나만 학습:**

```bash
naver-bot profile-refresh https://blog.naver.com/내아이디/123456789
```

**여러 소스를 한꺼번에 학습 (섞어도 됩니다):**

```bash
naver-bot profile-refresh \
  https://blog.naver.com/내아이디 \
  ./내가 직접 쓴 샘플.txt \
  --count 3
```

**수집할 포스트 수 지정 (`--count`):**

```bash
naver-bot profile-refresh https://blog.naver.com/내아이디 --count 10
```

> **Tistory 블로그도 됩니다:**
> ```bash
> naver-bot profile-refresh https://내아이디.tistory.com
> ```

---

**카테고리별로 다른 프로필 만들기 (`--profile`):**

글 종류마다 문체가 다르다면, 프로필을 나눠서 관리할 수 있습니다.

```bash
# 카페/음식 리뷰용 프로필
naver-bot profile-refresh https://blog.naver.com/내아이디/카페포스트URL \
  --profile cafe-review

# 제품 후기용 프로필
naver-bot profile-refresh https://blog.naver.com/내아이디/제품포스트URL \
  --profile product-review
```

학습이 완료되면:

```
Style profile 'default' saved → config/style_profiles/default.json
2 sample(s) used
```

---

### Step 2 — 블로그 초안 생성하기 (`draft`)

사진 경로와 짧은 메모를 주면, 학습한 문체로 블로그 초안을 생성합니다.

```bash
naver-bot draft 사진1.jpg 사진2.jpg 사진3.jpg "오늘 방문한 카페 너무 좋았다. 아메리카노가 진하고 분위기도 아늑해."
```

> 마지막 인자가 **메모**, 그 앞에 오는 것들이 모두 **사진 경로**입니다.

**다른 프로필로 생성:**

```bash
naver-bot draft 사진.jpg "신상 에어팟 써봤는데 노캔 대박" --profile product-review
```

생성이 완료되면:

```
Draft saved: draft-20260508-142530
```

초안 파일은 `drafts/draft-20260508-142530.json`에 저장됩니다.

---

### Step 3 — 초안 미리보기 (`preview`)

```bash
naver-bot preview draft-20260508-142530
```

터미널에 초안 내용이 출력됩니다:

```
# 분위기 맛집 카페 후기 ☕

Draft ID : draft-20260508-142530
Created  : 2026-05-08T14:25:30+00:00
Memo     : 오늘 방문한 카페 너무 좋았다...

Photos:
- 사진1.jpg
- 사진2.jpg
- 사진3.jpg

---

# 분위기 맛집 카페 후기

요즘 제가 찾던 딱 그런 카페를 발견했어요. {{이모티콘:설레}}

[사진: 사진1.jpg]

문을 열자마자 느껴지는 원두 향기가... (이하 생략)

[짤방: assets/memes/thumbsup.jpg]
```

> **`{{이모티콘:설레}}`** — 실제 블로그에 올릴 때 이모티콘으로 교체할 위치 표시입니다.  
> **`[사진: ...]`** — 사진을 삽입할 위치 표시입니다. 직접 블로그 에디터에서 교체하세요.

초안을 복사해서 네이버 블로그 에디터에 붙여넣은 뒤 사진과 이모티콘을 교체하면 완성입니다.

---

## 전체 워크플로우 요약

```
처음 한 번
──────────
1. uv sync                                    # 설치
2. .env 파일 작성                             # Claude 백엔드 설정
3. naver-bot init                             # 폴더 초기화
4. naver-bot profile-refresh <블로그URL>      # 문체 학습

이후 반복
──────────
5. naver-bot draft <사진...> <메모>           # 초안 생성
6. naver-bot preview <draft-id>              # 미리보기
7. 블로그 에디터에 붙여넣기 + 사진/이모티콘 교체
```

---

## 짤방 등록하기

자주 쓰는 짤방(반응 이미지)을 등록해두면, 초안 생성 시 메모 내용과 맞는 짤방을 자동 추천합니다.

```
assets/memes/        ← 짤방 이미지 파일을 여기에 넣으세요
```

> 짤방 인덱스 관리 커맨드(`meme-build`)는 현재 개발 중입니다.  
> 지금은 `config/meme_index.json`을 직접 편집해서 등록할 수 있습니다.

---

## 설정 옵션 전체 목록

`.env` 파일에서 설정할 수 있는 전체 옵션입니다.

| 환경변수 | 기본값 | 설명 |
|---------|-------|------|
| `ANTHROPIC_API_KEY` | (선택) | Anthropic SDK 백엔드를 강제로 사용할 때 필요한 API 키 |
| `NAVER_BOT_CLAUDE_BACKEND` | `auto` | Claude 호출 방식 (`auto`, `claude-code`, `anthropic-sdk`) |
| `NAVER_BOT_CLAUDE_COMMAND` | `claude` | Claude Code CLI 실행 명령 |
| `NAVER_BOT_CLAUDE_CLI_TIMEOUT_SECONDS` | `300` | Claude Code CLI 응답 대기 시간(초) |
| `NAVER_BOT_BLOG_URL` | `https://blog.naver.com/flowerbend` | 내 블로그 URL (profile-refresh 기본 blog_url) |
| `NAVER_BOT_OGQ_ARTWORK_ID` | `644e042a7d7f8` | OGQ 이모티콘 세트 ID |
| `NAVER_BOT_OGQ_NAME` | `세루리안` | OGQ 이모티콘 세트 이름 |
| `NAVER_BOT_CLAUDE_MODEL` | `claude-opus-4-7` | 사용할 Claude 모델 |
| `NAVER_BOT_CLAUDE_MAX_TOKENS` | `4000` | Claude 응답 최대 길이 |
| `NAVER_BOT_CONFIG_DIR` | `./config` | 설정 디렉터리 경로 |
| `NAVER_BOT_DRAFTS_DIR` | `./drafts` | 초안 저장 경로 |
| `NAVER_BOT_MEMES_DIR` | `./assets/memes` | 짤방 디렉터리 경로 |
| `NAVER_BOT_BROWSER_PROFILE_DIR` | `./browser-profile` | 브라우저 세션 경로 |

---

## 커맨드 레퍼런스

### `naver-bot init`

로컬 디렉터리 구조를 초기화합니다. 처음 한 번만 실행하세요.

```bash
naver-bot init
```

---

### `naver-bot profile-refresh`

블로그 글이나 로컬 파일을 읽어 문체 프로필을 생성/갱신합니다.

```bash
naver-bot profile-refresh [--profile <이름>] [--count <수>] <소스...>
```

| 파라미터 | 설명 | 기본값 |
|---------|------|-------|
| `<소스...>` | 블로그 URL 또는 로컬 파일 경로 (1개 이상) | (필수) |
| `--profile` | 프로필 이름 (영문 소문자, 숫자, `-`, `_`) | `default` |
| `--count` | URL당 수집할 포스트 수 | `5` |

**지원 소스:**
- 네이버 블로그 홈 URL → 최근 포스트 `--count`개 자동 수집
- 네이버 블로그 포스트 URL → 해당 포스트 1개
- Tistory 블로그 홈/포스트 URL
- 로컬 텍스트 파일 (`.txt`, `.md` 등)
- 위 소스를 여러 개 섞어서 지정 가능

---

### `naver-bot draft`

사진과 메모로 블로그 초안을 생성합니다.

```bash
naver-bot draft [--profile <이름>] <사진경로...> <메모>
```

| 파라미터 | 설명 | 기본값 |
|---------|------|-------|
| `<사진경로...>` | 사진 파일 경로 (1개 이상) | (필수) |
| `<메모>` | 글의 핵심 내용 (마지막 인자) | (필수) |
| `--profile` | 사용할 문체 프로필 이름 | `default` |

> 생성된 초안은 `drafts/draft-YYYYMMDD-HHMMSS.json`에 저장됩니다.

---

### `naver-bot preview`

저장된 초안을 터미널에 출력합니다.

```bash
naver-bot preview <draft-id>
```

| 파라미터 | 설명 |
|---------|------|
| `<draft-id>` | `draft-YYYYMMDD-HHMMSS` 형식의 초안 ID |

---

## 자주 묻는 질문

**Q. 네이버 블로그가 로그인이 필요한 경우 스크래핑이 안 되나요?**

`browser-profile/` 디렉터리에 브라우저 세션이 저장됩니다. 처음 `profile-refresh` 실행 시 브라우저 창이 뜨면 직접 로그인한 뒤 창을 닫으면, 이후부터는 로그인된 상태로 스크래핑됩니다.

**Q. Tistory 말고 다른 블로그도 되나요?**

네이버, Tistory 외에도 일반 웹페이지 URL을 소스로 쓸 수 있습니다. 다만 페이지 구조에 따라 텍스트 추출 품질이 달라질 수 있습니다.

**Q. 초안이 마음에 안 들면요?**

메모를 더 자세하게 작성하거나, `profile-refresh`를 더 많은 포스트로 재실행해서 문체 학습을 강화하세요. `--count 10` 정도로 올리면 프로필 품질이 좋아집니다.

**Q. 여러 카테고리 글을 쓰는데 문체가 달라요.**

`--profile` 옵션으로 카테고리별 프로필을 따로 만드세요.

```bash
naver-bot profile-refresh <카페후기URL> --profile cafe
naver-bot profile-refresh <제품후기URL> --profile product

naver-bot draft 사진.jpg "메모" --profile cafe
```

**Q. API 비용이 얼마나 드나요?**

`profile-refresh` 1회 약 5-15¢, `draft` 생성 1회 약 3-10¢ 수준입니다 (Claude Opus 기준). 반복 실행 시 캐싱으로 비용이 줄어듭니다.

---

## 앞으로 추가될 기능

- `meme-build` — 짤방 인덱스 자동 구축
- `publish` — 네이버 블로그에 직접 포스팅

---

## 라이선스

MIT
