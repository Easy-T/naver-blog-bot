# naver-blog-bot

내 블로그 문체를 학습해서, 사진과 메모만 주면 블로그 초안을 자동으로 써주는 로컬 CLI 도구입니다.

체험단 후기, 카페 방문기, 제품 리뷰처럼 **같은 패턴이 반복되는 글**을 자주 쓰는 분께 적합합니다.

---

## 어떻게 동작하나요?

```
내 블로그 URL
      │
      ▼
 [문체 학습]  ──────────────────────────────────────────────
      │                                                     │
      │  내 블로그 포스트를 읽어서                           │
      │  문체 프로필 + 실제 예시 포스트를 저장               │
      │                                                     │
      ▼                                                     │
 [짤방 등록]  ◀─── 이미지 파일 또는 URL                     │
      │                                                     │
      │  Claude Vision이 자동으로 태그 분석                  │
      │  감정/상황에 맞는 짤방 인덱스 구축                   │
      │                                                     │
      ▼                                                     │
 [초안 생성]  ◀─── 사진 경로 + 짧은 메모                    │
      │                                                     │
      │  학습한 문체 + 예시 포스트 + 메모를 Claude에 전달    │
      │  → 내 스타일로 쓴 블로그 초안 생성                  │
      │  → 초안 흐름에 맞는 짤방 자동 배치                  │
      │                                                     │
      ▼                                                     │
 [미리보기]                                                 │
      │                                                     │
      │  브라우저에서 레이아웃 확인                          │
      │  내용이 클립보드에 자동 복사                         │
      │  → 네이버 SmartEditor에 붙여넣기                    │
      │                                                     │
      └─────────────────────────────────────────────────────
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
| xclip 또는 xsel (WSL2) | 클립보드 복사 기능 사용 시 필요 (`sudo apt install xclip`) |

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
│   └── style_profiles/   ← 학습한 문체 프로필 + 예시 포스트가 저장되는 곳
├── drafts/               ← 생성된 초안 + HTML 미리보기가 저장되는 곳
├── assets/
│   └── memes/            ← 짤방 이미지를 여기 넣으세요
└── browser-profile/      ← 브라우저 세션 (자동 관리)
```

---

## 사용법

### Step 1 — 내 문체 학습시키기 (`profile-refresh`)

AI가 내 블로그 글을 읽고 "이 사람은 이런 식으로 쓰는구나"를 파악합니다.
결과는 `config/style_profiles/default.json`과 `config/style_profiles/default-examples.json`에 저장됩니다.

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

> **Tistory 블로그도 됩니다:**
> ```bash
> naver-bot profile-refresh https://내아이디.tistory.com
> ```

**카테고리별로 다른 프로필 만들기 (`--profile`):**

```bash
# 카페/음식 리뷰용 프로필
naver-bot profile-refresh https://blog.naver.com/내아이디/카페포스트URL \
  --profile cafe-review

# 제품 후기용 프로필
naver-bot profile-refresh https://blog.naver.com/내아이디/제품포스트URL \
  --profile product-review
```

---

### Step 2 — 짤방 등록하기 (선택)

자주 쓰는 짤방(반응 이미지)을 등록해두면, 초안 생성 시 Claude가 글 흐름을 분석해 적절한 위치에 자동으로 배치합니다.

**파일로 등록:**

```bash
naver-bot meme-add assets/memes/thumbsup.jpg
```

```
Added: thumbsup.jpg (tags: 만족, 추천)
```

**URL로 바로 다운로드 + 등록:**

```bash
naver-bot meme-fetch https://example.com/funny-reaction.gif
```

**폴더 전체 일괄 등록 (`meme-build`):**

`assets/memes/`에 이미지를 넣어두고 한 번에 처리합니다.

```bash
naver-bot meme-build
```

```
Tagged: thumbsup.jpg
Tagged: surprised.png
Done: 2 new image(s) tagged, 0 existing skipped.
```

> Claude Vision이 이미지를 분석해 `tags`와 `use_cases`를 자동으로 붙여줍니다.
> 이미 등록된 이미지는 건너뜁니다.

---

### Step 3 — 블로그 초안 생성하기 (`draft`)

사진 경로와 짧은 메모를 주면, 학습한 문체로 블로그 초안을 생성합니다.
등록된 짤방이 있으면 초안 흐름에 맞게 자동으로 배치됩니다.

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
Draft saved: draft-20260530-142530
```

---

### Step 4 — 초안 미리보기 (`preview`)

```bash
naver-bot preview draft-20260530-142530
```

- **브라우저가 자동으로 열립니다** — 네이버 블로그 유사 레이아웃으로 렌더링
- **내용이 클립보드에 복사됩니다** — 네이버 SmartEditor에 바로 붙여넣기 가능

브라우저에서 확인 후 네이버 블로그 에디터에 붙여넣어 사진과 이모티콘만 교체하면 완성입니다.

미리보기 파일은 `drafts/draft-20260530-142530.html`에 저장됩니다.

> **`{{이모티콘:설레}}`** — 실제 블로그에 올릴 때 이모티콘으로 교체할 위치 표시입니다.
> **`[사진: ...]`** — 사진을 삽입할 위치 표시입니다. 직접 블로그 에디터에서 교체하세요.
> **`[짤방: id]`** — 등록된 짤방을 삽입할 위치입니다. 해당 이미지를 업로드하세요.

---

## 전체 워크플로우 요약

```
처음 한 번
──────────
1. uv sync                                         # 설치
2. .env 파일 작성                                  # Claude 백엔드 설정
3. naver-bot init                                  # 폴더 초기화
4. naver-bot profile-refresh <블로그URL>           # 문체 학습
5. naver-bot meme-add <이미지> 또는               # 짤방 등록 (선택)
   naver-bot meme-build

이후 반복
──────────
6. naver-bot draft <사진...> <메모>               # 초안 생성
7. naver-bot preview <draft-id>                   # 브라우저 확인 + 클립보드 복사
8. 네이버 에디터에 붙여넣기 + 사진/이모티콘 교체
```

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

---

### `naver-bot profile-refresh`

블로그 글이나 로컬 파일을 읽어 문체 프로필을 생성/갱신합니다.
URL 소스를 사용하면 실제 예시 포스트도 함께 저장되어 초안 품질이 향상됩니다.

```bash
naver-bot profile-refresh [--profile <이름>] [--count <수>] <소스...>
```

| 파라미터 | 설명 | 기본값 |
|---------|------|-------|
| `<소스...>` | 블로그 URL 또는 로컬 파일 경로 (1개 이상) | (필수) |
| `--profile` | 프로필 이름 (영문 소문자, 숫자, `-`, `_`) | `default` |
| `--count` | URL당 수집할 포스트 수 | `5` |

---

### `naver-bot meme-add`

이미지 파일을 분석하여 짤방 라이브러리에 등록합니다.

```bash
naver-bot meme-add <이미지파일>
```

Claude Vision이 이미지를 분석해 감정 태그와 사용 상황을 자동으로 붙여줍니다.

---

### `naver-bot meme-fetch`

URL에서 이미지를 다운로드하여 짤방 라이브러리에 등록합니다.

```bash
naver-bot meme-fetch <이미지URL>
```

---

### `naver-bot meme-build`

`assets/memes/` 폴더의 이미지를 전체 스캔하여 등록되지 않은 이미지를 자동으로 태깅합니다.

```bash
naver-bot meme-build
```

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

---

### `naver-bot preview`

저장된 초안을 브라우저에서 열고 클립보드에 복사합니다.

```bash
naver-bot preview <draft-id>
```

실행 시:
- 브라우저에서 `drafts/<draft-id>.html`이 자동으로 열립니다
- 초안 본문이 클립보드에 복사됩니다 (WSL2는 `xclip` 또는 `xsel` 필요)

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

**Q. 짤방이 없어도 초안 생성이 되나요?**

네. 짤방이 등록되지 않은 경우 문맥 기반 짤방 배치 단계는 자동으로 건너뜁니다.

**Q. 클립보드 복사가 안 돼요 (WSL2).**

WSL2 환경에서 클립보드 연동을 위해 `xclip`이 필요합니다.

```bash
sudo apt install xclip
```

**Q. API 비용이 얼마나 드나요?**

`profile-refresh` 1회 약 5-15¢, `draft` 생성 1회 약 3-10¢ 수준입니다 (Claude Opus 기준). 반복 실행 시 캐싱으로 비용이 줄어듭니다. Claude Code 구독 사용 시 별도 API 비용 없습니다.

---

## 앞으로 추가될 기능

- `publish` — 네이버 블로그에 직접 포스팅 (Playwright 기반)

---

## 라이선스

MIT
