# Naver Category Filter via PostTitleListAsync API — Design Spec

Created: 2026-05-31
Project: naver-blog-bot
RPI-Cycle: 8

## 1. Problem

`profile-refresh ...?categoryNo=N`이 카테고리를 필터하지 못한다. 모든 categoryNo가 동일한 "최근 글 전체"를 반환해, 카테고리별 named 프로필이 사실상 같은 데이터로 학습된다 (cycle 7에서 카테고리 필터를 실제 검증 없이 통과시킨 것이 원인).

**probe로 확정한 근본 원인 (검증 완료):**

| 엔드포인트 | categoryNo 필터 |
|---|---|
| `m.blog.naver.com/{id}` (현재 사용, 모바일 홈) | ❌ 무시, 항상 최근 글 |
| `m.blog.naver.com/PostList.naver?categoryNo=` | ❌ 무시 |
| `blog.naver.com/{id}?categoryNo=` (PC iframe) | ❌ 무시 |
| **`blog.naver.com/PostTitleListAsync.naver?blogId=&categoryNo=&countPerPage=&currentPage=`** | ✅ **정확히 필터** |

`PostTitleListAsync.naver`는 JSON을 반환하고 `totalCount`가 카테고리별 정확한 글 수(맛집=5, 연애=2)와 일치한다. `postList[].logNo` + `categoryNo`를 담는다.

## 2. Goal

1. `profile-refresh ...?categoryNo=N`이 해당 카테고리 글만 수집한다.
2. categoryNo가 없으면 기존 동작(모바일 홈 최근 글)을 유지한다 — 하위 호환.
3. 본문 파서(`parse_post_html`)와 기존 명령 시그니처는 불변.
4. 단위 테스트는 오프라인·결정론 유지 (실제 네이버 호출 금지).

## 3. Approach

### 3.1 카테고리 분기

`naver.collect_blog_post_urls(page, url, count)` 변경:
- URL 쿼리에 `categoryNo`가 있으면 → `PostTitleListAsync.naver` JSON API 경로
- 없으면 → 기존 모바일 홈 live DOM 경로 (cycle 7, 변경 없음)

### 3.2 JSON API 경로

신규 헬퍼:
- `category_list_api_url(url) -> str | None`: URL에서 blogId·categoryNo를 파싱해 `PostTitleListAsync.naver` URL 생성. categoryNo 없으면 None.
- `_select_post_urls_from_titlelist(payload: dict, blog_id: str, count: int) -> list[str]`: 순수 함수. JSON dict를 받아 `postList[].logNo`로 `https://m.blog.naver.com/{blogId}/{logNo}` URL 리스트 생성, count 제한.

`collect_blog_post_urls`에서 categoryNo가 있으면:
- `page.goto(blog_home)` (쿠키 컨텍스트 확보) 후
- `page.evaluate(fetch(api_url))`로 JSON 텍스트 취득
- JSON 파싱(네이버는 가끔 `)]}',` 프리픽스 → strip) 후 `_select_post_urls_from_titlelist`로 URL 생성
- 비면 ValueError

### 3.3 파싱 주의

- 네이버는 가끔 JSON 앞에 `)]}',` XSSI 프리픽스를 붙임 → strip 후 `json.loads`.
- probe로 확인 결과 본문은 표준 JSON이라 `json.loads`로 충분. 파싱 실패 시 명확한 ValueError로 처리(정규식 fallback은 과설계 — 미적용).
- title의 HTML 엔티티/URL 인코딩은 URL 생성에 불필요하므로 무시 (본문은 scrape_post가 따로 가져옴).

## 4. Out of Scope

- tistory 카테고리 — 네이버만.
- 본문 파서 변경.
- 페이지네이션(currentPage>1) — count는 첫 페이지(countPerPage=30) 내로 충분.
- 자동 로그인.

## 5. Files

| 파일 | 변경 |
|------|------|
| `src/naver_blog_bot/blog_scraper/adapters/naver.py` | `category_list_api_url()`, `_select_post_urls_from_titlelist()` 신규, `collect_blog_post_urls` categoryNo 분기 |
| `tests/unit/test_blog_scraper_naver.py` | 순수 함수 2개 테스트 + categoryNo 분기 mock-page 테스트 |

## 6. Risks

- `page.evaluate` fetch는 same-origin 필요 → blog.naver.com 홈에서 호출 (api도 blog.naver.com). OK.
- JSON 비표준 형태 → 정규식 fallback으로 방어.
- API 응답 형태 변경 가능성 → fallback + 명확한 ValueError 메시지.

## 7. Success Criteria

- `_select_post_urls_from_titlelist`가 샘플 JSON dict에서 logNo 기반 모바일 URL을 count 제한으로 반환 (단위 테스트).
- `category_list_api_url`이 categoryNo 유무에 따라 URL/None 반환 (단위 테스트).
- `collect_blog_post_urls`가 categoryNo URL에서 JSON 경로를 타고 mock fetch 결과로 URL 수집 (mock 테스트).
- 전체 테스트 그린 + ruff.
- (수동) `profile-refresh ?categoryNo=10`과 `?categoryNo=6`이 **서로 다른** 글을 수집.

## 8. Self-Review

- Placeholder 없음.
- 범위: naver.py + 테스트만. 본문 파서·시그니처 불변.
- 모호성: categoryNo는 URL에서 파싱(시그니처 불변), JSON fallback 명시.
- 오프라인 테스트 유지 (deny-pattern 준수).
