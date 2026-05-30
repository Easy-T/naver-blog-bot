# Naver Scraper Post-URL Collection Fix + Category Support — Design Spec

Created: 2026-05-30
Project: naver-blog-bot
RPI-Cycle: 7

## 1. Problem

`profile-refresh`가 실제 네이버 블로그 URL에서 실패한다 (`ValueError: no posts found`).

**직접 진단 결과 (probe로 검증 완료 — 2단계로 좁혀짐):**

진단 1차 (custom parser): `page.content()` 정적 HTML을 커스텀 파서로 처리 → 앵커 0개. live DOM 전환으로 1차 해결 (Task 1·2, 커밋 완료).

진단 2차 (엔드포인트 — **진짜 근본원인**): live DOM 전환 후에도 실패가 재현. probe로 동일 프로필·동일 시점 3개 엔드포인트를 비교:
```
NAVER_HOME  logged_out: True            ← 봇 persistent 프로필은 로그아웃 상태
MOBILE_POSTLIST (PostList.naver)  total=29   posts=0    ← 현재 코드가 쓰는 곳
MOBILE_HOME (m.blog.naver.com/{id}) total=214 posts=31  ← 안정적으로 31개 ✅
PC_MAINFRAME (iframe)             total=484  posts=5
```
- `post_list_url`이 만드는 `m.blog.naver.com/PostList.naver?blogId=X` 는 **레거시 엔드포인트**로 포스트 앵커 0개(드물게 리다이렉트로 채워져 비결정적).
- **모바일 블로그 홈** `m.blog.naver.com/{blogId}` 은 **로그아웃 상태에서도 공개 글 31개를 안정 렌더**.
- 즉 공개 글 학습은 **로그인 불필요** — 엔드포인트만 모바일 홈으로 바꾸면 된다.
- **본문 파서(`parse_post_html`)는 정상** (probe: `has_se_main: True`, 21블록).
- `post_list_url`이 `categoryNo`를 무시 → 카테고리별 학습 불가.

**login 기능의 가치:** 공개 글엔 불필요하지만, 비공개·이웃공개 글 학습과 세션 안정성을 위해 사용자가 명시 요청 → 이번 사이클에 함께 구현.

## 2. Goal

1. 실제 네이버 블로그 홈 URL에서 `profile-refresh`가 최근 포스트를 정상 수집한다.
2. 카테고리 URL(`?categoryNo=N`)을 주면 해당 카테고리 글만 수집해 named 프로필로 저장할 수 있다.
3. 정상 작동하는 본문 파서는 그대로 둔다.
4. 단위 테스트는 오프라인·결정론 유지 (실제 네이버 호출 금지).

## 3. Approach

### 3.1 Live DOM 기반 URL 수집

`naver.collect_blog_post_urls(page, url, count)`를 변경:
- 기존: `page.goto` → `page.content()` → `collect_post_urls(html, ...)` (커스텀 파서)
- 변경: `page.goto` → `page.wait_for_selector("a")` → `hrefs = page.eval_on_selector_all("a", "els => els.map(e => e.href)")` → 순수 함수로 필터링

### 3.2 추출 로직을 순수 함수로 분리 (테스트 가능성)

신규 순수 함수 `_select_post_hrefs(hrefs: list[str], base_url: str, count: int) -> list[str]`:
- 이미 추출된 href 리스트를 받아 `_resolve_post_url`로 정규화·중복제거·count 제한.
- 기존 `collect_post_urls(html, ...)`의 HTML 파싱 부분만 제거하고 필터 로직 재사용.
- 단위 테스트는 href 리스트 → URL 리스트로 검증 (브라우저 불필요).

### 3.3 엔드포인트 수정 (진짜 근본원인 — Task 4)

`naver.post_list_url(url)` 변경:
- 기존: `m.blog.naver.com/PostList.naver?blogId=X&currentPage=1` (레거시, 포스트 0개)
- 변경: `m.blog.naver.com/{blogId}` (모바일 블로그 홈, 공개 글 안정 렌더)
- `categoryNo`가 있으면 `m.blog.naver.com/{blogId}?categoryNo=N`로 보존.

`naver.collect_blog_post_urls` 에 **렌더 타이밍 대비 폴링** 추가:
- networkidle 후 포스트 앵커가 0개면 1초 간격 최대 5회 재시도 (JS 늦은 렌더 대비). 비결정성 제거.

### 3.4 로그인 세션 (Task 5)

`naver-bot login` 명령 추가:
- headed(`headless=False`) persistent context를 `browser-profile/`로 실행.
- 네이버 로그인 페이지로 이동 → 사용자가 직접 로그인 → 터미널에서 Enter → 세션 저장 후 종료.
- 이후 `profile-refresh`가 같은 `browser-profile/`을 재사용해 로그인 세션으로 스크래핑.
- WSLg 디스플레이 확인됨(DISPLAY=:0, /mnt/wslg).

`naver.is_blog_url(url)`:
- `?categoryNo=N`이 붙은 블로그 홈 URL이 여전히 blog(목록)으로 인식되는지 테스트로 확인.

### 3.4 `_resolve_post_url`, 본문 파서

- 변경 없음. `_resolve_post_url`은 정규화에 계속 사용.
- `parse_post_html` 및 `_classify_se_component`/`_parse_se_main_container`/`_parse_legacy_area` 전부 유지.

## 4. Out of Scope

- **tistory 어댑터** — 동일 잠재 버그(정적 파서)가 있으나 사용자 사용 대상이 네이버라 이번 범위 제외 (향후 사이클에서 동일 패턴 적용).
- **자동 로그인** — 아이디/비번 자동 입력은 하지 않음. 사용자가 headed 브라우저에서 직접 로그인 (CAPTCHA/2FA 대응 + ToS 안전).
- few-shot/짤방/preview/publish 등 기존 기능 — 변경 없음.

## 5. Files

| 파일 | 변경 |
|------|------|
| `src/naver_blog_bot/blog_scraper/adapters/naver.py` | (Task 1·2 완료) live DOM화 + `_select_post_hrefs`. (Task 4) `post_list_url` 엔드포인트를 모바일 홈으로 + categoryNo, `collect_blog_post_urls` 폴링 |
| `src/naver_blog_bot/blog_scraper/login.py` | (Task 5 신규) headed persistent context 로그인 헬퍼 |
| `src/naver_blog_bot/cli.py` | (Task 5) `login` 명령 추가 |
| `tests/unit/test_blog_scraper_naver.py` | (Task 4) `post_list_url` 엔드포인트/카테고리 테스트, 폴링 mock 테스트 갱신 |
| `tests/unit/test_login.py` | (Task 5 신규) login 헬퍼/명령 테스트 |
| `docs/ai-context/architecture.md` | (Task 5) headed 로그인 세션 ADR append |

## 6. Risks

- `eval_on_selector_all`의 `e.href`는 절대 URL을 반환 → `_resolve_post_url`이 절대/상대 모두 처리하는지 확인 (현재 `urljoin` 사용하므로 OK).
- 네이버가 같은 포스트를 PC/모바일 두 형태로 노출 → `_resolve_post_url` 정규화가 중복 제거하는지 테스트로 확인.
- mock-page 테스트: 가짜 `page` 객체에 async `eval_on_selector_all`/`goto`/`wait_for_selector`를 구현 (기존 테스트의 fake page 패턴 재사용).

## 7. Success Criteria

- `_select_post_hrefs`가 혼합 href 리스트에서 유효 포스트 URL만, 중복 없이, count 제한으로 반환 (단위 테스트).
- `post_list_url`이 `categoryNo`를 보존/생략 양쪽 케이스 통과 (단위 테스트).
- `collect_blog_post_urls`가 mock page의 앵커 리스트로 URL을 수집 (mock 테스트).
- 전체 테스트 그린 + ruff 통과.
- (수동 확인) 실제 `profile-refresh https://blog.naver.com/flowerbend --count 3`가 포스트를 수집해 프로필+examples 저장.

## 8. Self-Review

- Placeholder 없음.
- 범위: DOM 수집 + 카테고리만. 로그인/tistory 명시 제외.
- 모호성: categoryNo는 URL에서 파싱(시그니처 불변) — 명시됨.
- 테스트 오프라인 유지 (deny-pattern 준수) — 명시됨.
