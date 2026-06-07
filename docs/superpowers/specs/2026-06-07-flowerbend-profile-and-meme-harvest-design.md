# 설계: flowerbend 종합 프로필 + 짤방 자동 수집·학습

- 작성일: 2026-06-07
- 상태: 승인됨 (브레인스토밍 완료)
- 별칭: "이방봉" 프로필 (= 전 카테고리 종합 프로필, id `flowerbend`)
- 관련: `blog_scraper/`, `meme_library/`, `style_profiler/`, `post_generator/generator.py`, `cli.py`

## 배경 / 문제

사용자 피드백: 생성된 초안에 블로그 주인이 실제로 쓰는 "짤방"(상황에 맞는 반응 이미지)이 전혀 들어가지 않는다. 조사 결과:

1. **라이브러리가 사실상 비어 있다.** `config/meme_index.json`에는 일반 이모지 PNG 3개(`meme_smile`, `meme_surprise`, `emoji_u1f602`)만 있고, 진짜 짤방이 없다. 배치할 짤방 자체가 없으니 초안에 나올 수가 없다.
2. **배치 로직은 정상.** 생성기는 2단계로 동작한다 — ① 메모 기반 후보 선별, ② 초안 완성 후 `_place_memes_in_draft()`가 LLM 2차 패스로 `[짤방: id]`를 흐름에 맞는 문단에 삽입. 즉 라이브러리만 채워지면 작동한다.
3. **발굴은 원래 없었다.** README·2026-05-29 spec 기준 짤방 파이프라인은 처음부터 "등록(`meme-add`/`meme-fetch`) → vision 태깅 → 자동 배치"였고, "적절한 짤방을 자동으로 찾아오는" 발굴 단계는 spec·코드에 존재한 적이 없다.
4. **스크래퍼가 이미지 URL을 버린다.** `blog_scraper`의 `ImageBlock`은 `alt`만 보존하고 `src`를 버린다. 그래서 주인이 실제 쓰는 짤방을 가져올 방법이 없고, 프로필 학습도 모든 이미지를 `[이미지]`로 뭉개 "짤방을 언제 쓰는지"를 학습한 적이 없다.

또한 사용자는 카테고리와 무관하게 flowerbend 전체 글을 학습한 **단일 종합 프로필**을 원한다(별칭 "이방봉"). 한글은 CLI 인자에서 깨지고 `validate_profile_name`이 `[a-z0-9_-]`만 허용하므로 프로필 id는 `flowerbend`로 한다.

## 목표 / 성공 기준 (goal-driven — 충족할 때까지 반복)

1. flowerbend 전 카테고리·모든 글을 학습한 단일 프로필 `config/style_profiles/flowerbend.json` 생성. 카테고리 무관하게 주인 문체로 초안 작성 가능.
2. 주인이 실제 쓰는 짤방을 블로그에서 자동 수집·분류·태깅해 전역 라이브러리(`config/meme_index.json`)에 등록.
3. 프로필이 "언제·어떤 상황에 짤방을 쓰는지"를 7번째 축(`meme_usage_patterns`)으로 학습.
4. `--profile flowerbend`로 생성한 초안이 흐름에 맞는 **진짜 짤방**을 배치한다(빈 라이브러리/일반 이모지가 아닌 수집된 자산).
5. **기존 명령어 통합**: URL 소스로 `profile-refresh`를 실행하면 같은 스크랩에서 짤방도 함께 학습한다(별도 명령 없음). `--no-memes`로 opt-out.
6. 동일 이미지 재실행 시 분류 vision 호출 0회(content-hash 캐시).
7. 기존 테스트 전부 통과 + 신규 단위 테스트 통과.

## 비목표 (YAGNI)

- 자동 발행(publish)은 여전히 범위 밖.
- 웹 검색 기반 짤방 소싱(주인 블로그 외부에서 검색·수집)은 하지 않는다.
- GIF 애니메이션 특수 처리(프레임 분석 등) 안 함 — 네이버 붙여넣기는 수동이므로 원본 파일을 자산으로 보존하는 것으로 충분.
- 카테고리별 분리 프로필은 만들지 않는다(`flowerbend`는 단일 종합 프로필; 기존 review/food/love는 그대로 공존).
- 수집 짤방 사람 검수 게이트 없음(사용자 결정: 자동 등록).

## 핵심 통찰 — 1회 스크랩이 둘 다 먹인다

전체 블로그를 한 번 스크랩하면 **텍스트는 프로필(A)로, 이미지는 짤방(B)으로** 흘려보낼 수 있다. 이미지 분류 결과(짤방 여부)를 텍스트에 `[짤방]`/`[사진]`으로 주석 달면, 프로필이 짤방 사용 습관(`meme_usage_patterns`)까지 학습한다. 그래서 분류 패스가 레지스트리와 프로필 양쪽을 먹이는 공통 의존이 된다.

## 파이프라인 (의존 순서)

```
1. 전체 블로그 스크랩 (모든 카테고리 → 모든 글)
     · 텍스트 블록 + 이미지 src URL + 주변 문맥 캡처      ← 스크래퍼 확장
2. 이미지 분류 패스
     · 다운로드(content-hash 캐시) → vision 1콜:
       {is_meme, tags, use_cases, alt}
     · 반복 등장(여러 글) = 짤방 강신호
3. 짤방 레지스트리 구축
     · hash로 중복 제거 → 여러 등장의 문맥을 합쳐 use_cases 보강
     · frequency 기록 → 자동 등록
4. flowerbend 프로필 빌드
     · [짤방]/[사진] 주석 텍스트 → 배치 map-reduce 집계
     · 7축 프로필(+ meme_usage_patterns) + 예시 저장
```

## 설계 (컴포넌트)

### ① 스크래퍼 확장 — `blog_scraper/`

- `ImageBlock`에 `src: str = ""` 추가. 네이버/레거시 어댑터의 `_img_block_from_node`·`_classify_se_component`에서 실제 이미지 URL을 채운다(lazy-load 대비 `data-lazy-src` 등 fallback). 기존 동작 무해(기본값 `""`, `to_structured_text`는 그대로 `[이미지]`).
- 전 카테고리 열거: `category-list` API(`m.blog.naver.com/api/blogs/<id>/category-list`)로 모든 `categoryNo` 수집 → 카테고리별 `PostTitleListAsync.naver`를 **페이지네이션**(currentPage 루프)으로 끝까지 긁어 모든 `logNo` 수집 → dedupe. 현재 `_collect_category_post_urls`는 currentPage=1만 가져오므로 이 부분을 확장.
- 신규 진입점: `scrape_blog_all(url, settings) -> list[PostDocument]` (전 카테고리·전 글). 기존 `scrape(url, count, settings)`는 유지.

### ② 짤방 수집기 — `meme_harvester/` (신규 모듈)

`style_profiler`·`photo_describer`와 같은 작은 단위.

- 입력: 스크랩된 `PostDocument` 목록에서 추출한 `(image_src, context_text)` 리스트. `context_text`는 해당 `ImageBlock` 직전/직후 `TextBlock` 내용.
- 처리(이미지별):
  1. 다운로드(httpx, `Referer`/`User-Agent` 헤더 부여, 타임아웃, 실패 시 skip).
  2. content-hash(SHA-256) 계산 → 사이드카 캐시(`config/.harvest-cache.json` 또는 설정 경로) 조회. 히트면 vision 생략.
  3. vision 1콜로 `{is_meme: bool, tags: [...], use_cases: [...], alt: "..."}` 획득(JSON only, `_extract_meme_json` 재사용).
- 자동 등록 게이트(단일·명확): **vision이 `is_meme=true`로 판정한 이미지만 등록.** 콘텐츠 사진(`is_meme=false`)은 제외.
- 같은 hash의 여러 등장 문맥을 합쳐 `use_cases`를 보강하고 `frequency`(등장 글 수)를 집계. `frequency`는 후보 랭킹과 `use_cases` 보강에 쓰며, **반복 등장은 짤방일 가능성을 높이는 보조 근거로 분류 프롬프트에 함께 제공**해 판정 정확도를 높인다(게이트는 어디까지나 `is_meme`).
- 출력: `MemeAsset` 목록 → `add_or_update_meme`로 기존 인덱스에 병합 저장. 자산 파일은 `assets/memes/`에 저장(`ensure_in_memes_dir` 패턴 재사용, 다운로드 바이트 기록).
- 공개 함수: `harvest_memes(documents, vision_client, *, memes_dir, cache_path) -> list[MemeAsset]`.

### ③ 스키마 변경 (모두 additive)

- `MemeAsset` + `frequency: int = 1` (자주 쓰는 짤방 우선 랭킹용; 기존 인덱스 로드 시 기본값으로 무해).
- `StyleProfile` + `meme_usage_patterns: list[str] = Field(default_factory=list)` (7번째 축). `to_cache_text`에 포함, `refresh.py` 프롬프트에 항목 추가, 기존 프로필 로드 시 기본값으로 무해.

### ④ 프로필 빌드(A) 강화 — `style_profiler/`

- 대량 글을 한 프롬프트에 다 못 넣으므로 **배치 요약 → 병합(map-reduce)**: 글을 N개 묶음으로 나눠 각 묶음에서 6+1축 부분 프로필을 추출 → 마지막에 병합 LLM 콜로 통합 프로필 1개 산출. `refresh_style_profile`를 배치 대응으로 확장(소량이면 단일 콜 그대로).
- 입력 텍스트는 ②의 분류 결과로 `[짤방]`/`[사진]` 주석을 반영해 `meme_usage_patterns`를 학습.
- 예시(`FewShotRepository`)는 카테고리 다양성을 갖도록 선택(상한 3 유지 또는 소폭 상향은 구현 시 결정; 기본 3 유지).

### ⑤ 생성기/매칭(B) 통합 — `post_generator/generator.py`

- 후보 선별: 약한 `candidates_for_memo(memo)`(메모 부분일치) 대신 **frequency 랭킹** 기반으로 후보를 추리고, 배치는 기존 `_place_memes_in_draft()`(초안 전체 + 카탈로그 LLM 패스)를 유지. 라이브러리가 실해지면 배치가 정상 작동.
- 프로필의 `meme_usage_patterns`를 캐시 컨텍스트(`style_profile.to_cache_text()`)로 자연히 투입 → 배치 판단이 주인답게.
- 짤방 라이브러리는 프로필 무관 전역이므로 **review/food/love 기존 프로필도 자동 혜택**.

### ⑥ CLI 통합 — `cli.py`

- 별도 명령 추가 없음. `profile-refresh`에 짤방 학습을 흡수:
  - URL 소스로 실행 시, 스크랩된 문서의 이미지를 ②로 수집해 전역 라이브러리에 자동 등록(로컬 파일 소스는 이미지가 없어 자동 skip).
  - `--all-categories` 플래그(기본 off): 켜면 전 카테고리·전 글(`scrape_blog_all`)을 사용(종합 프로필용). off면 기존 `--count` 동작.
  - `--no-memes` 플래그(기본 off): 켜면 짤방 수집 생략(스타일만).
- 종합 프로필 생성 표준 커맨드: `profile-refresh https://blog.naver.com/flowerbend --profile flowerbend --all-categories`.

## 데이터 흐름

```
blog url
  → scrape_blog_all (전 카테고리·전 글)         (blog_scraper)
  → PostDocument[] (text blocks + ImageBlock.src + context)
  → 이미지 분류/수집 (download+hash+vision, 캐시) (meme_harvester)
      ├─ 짤방 → dedupe/문맥집계 → meme_index 자동 등록
      └─ [짤방]/[사진] 주석 텍스트
  → 프로필 빌드 (batched map-reduce, 7축)        (style_profiler)
  → flowerbend.json + flowerbend-examples.json
  (이후) draft → 생성기가 meme_index + meme_usage_patterns로 짤방 배치
```

## 에러 처리

- 이미지 다운로드 실패/타임아웃 → 해당 이미지 skip, 전체 중단 금지.
- 네이버 CDN 403 → `Referer`(글 URL)/`User-Agent` 부여 재시도, 그래도 실패면 skip + 로그.
- vision 실패/타임아웃 → 해당 이미지 미분류 skip(짤방 미등록), 진행 계속.
- 캐시 파일 손상/파싱 실패 → 무시하고 재생성(예외 전파 금지).
- 카테고리/페이지 API가 빈 응답/HTML 폴백 → 기존 `_parse_naver_json`의 logNo 정규식 폴백 재사용.
- 프로필 빌드 배치 일부 실패 → 성공한 배치만으로 병합(부분 실패 허용), 전부 실패면 에러.

## 테스트 전략

- 스크래퍼: `ImageBlock.src` 캡처(목 HTML), 전 카테고리 열거 + 페이지네이션(목 API 응답), lazy-src fallback.
- 수집기: vision JSON 파싱, content-hash 중복 제거, 반복 등장=짤방 기준, 캐시 히트 시 호출 0회, 다운로드/ vision 실패 skip 폴백, 문맥 집계로 use_cases 보강.
- 스키마: `MemeAsset.frequency`/`StyleProfile.meme_usage_patterns` 기본값 하위호환, `to_cache_text` 포함.
- 프로필: 배치 map-reduce 병합, `meme_usage_patterns` 산출, `[짤방]` 주석 반영.
- 생성기: frequency 랭킹 후보 선별, 배치 회귀(기존 동작 보존), `--no-memes`/`--all-categories` CLI 분기.
- 회귀: 기존 blog_scraper/meme_library/style_profiler/post_generator/cli 테스트 전부 통과.

## 아키텍처 영향 (ADR 필요)

- 신규 모듈 `meme_harvester` 추가, `blog_scraper` 스키마 변경(이미지 URL 보존), `style_profiler` 7번째 축 + 배치 빌드, `profile-refresh` 데이터 흐름 변경(스크랩→분류→레지스트리+프로필) → **ADR-011** 작성 대상(§5). 구현/클로즈아웃 단계에서 `docs/ai-context/architecture.md`에 append.
- `CLAUDE.md` Modules 섹션에 `meme_harvester` 한 줄 추가(세션 종료 직전).
- `docs/ai-context/domain-glossary.md`: "짤방" 항목에 자동 수집 경로 반영, "이방봉/flowerbend 프로필" 용어 추가.

## 리스크 / 결정 사항

- **저작권**: 수집 짤방은 제3자 IP를 주인이 이미 공개적으로 재사용 중인 것. 주인 본인 블로그용으로 동일 관행을 복제하는 것이므로 주인이 이미 감수하는 위험 수준과 동일. 사용자 수락. spec에 명시.
- **분류 정확도(자동 등록)**: vision `is_meme` 판정을 단일 게이트로 사용. 반복 등장(frequency) 신호를 분류 프롬프트의 보조 근거로 제공해 정확도를 높이고, 콘텐츠 사진 오등록을 억제.
- **볼륨/시간**: 전체 블로그 스크랩은 글당 Playwright goto로 느림(1회성 학습 작업). 분류 캐시로 재실행 비용 상쇄.
- **네이버 이미지 접근**: CDN(pstatic.net)이 Referer 요구 가능 → 헤더 부여, 실패 skip.

## 구현 단계 (플랜에서 phase로 분리)

- **P1**: 스크래퍼 확장 — `ImageBlock.src` 캡처 + 전 카테고리/페이지네이션 열거(`scrape_blog_all`). 단독 테스트 가능.
- **P2**: `meme_harvester` 모듈 + `MemeAsset.frequency` — 다운로드/분류/중복제거/문맥집계/자동 등록.
- **P3**: 프로필 빌드 강화 — `StyleProfile.meme_usage_patterns`, 배치 map-reduce, `[짤방]` 주석; `profile-refresh`에 짤방 수집 통합(`--all-categories`/`--no-memes`).
- **P4**: 생성기 매칭 통합(frequency 랭킹 + `meme_usage_patterns`) + 실데이터 검증: 실제 `profile-refresh ... --profile flowerbend --all-categories` 실행으로 `flowerbend.json`·짤방 라이브러리 산출, 샘플 드래프트가 진짜 짤방을 배치하는지 확인.
