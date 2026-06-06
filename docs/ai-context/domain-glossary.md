# Domain Glossary — naver-blog-bot

> 사내 용어 ↔ 코드 식별자 매핑. AI가 도메인 언어를 정확히 사용하도록.
> 새 용어 등장 시 메인이 confidence < 80%면 사용자에게 확인 후 자동 추가.

## Domain → Code

| 도메인 용어 | 코드 식별자 | 비고 |
|---|---|---|
| 체험단 후기 | `Draft`, `PostGenerator.generate()` | 사진과 메모를 바탕으로 생성하는 리뷰형 네이버 블로그 초안 |
| 스타일 프로필 | `StyleProfile`, `StyleProfile.emoticon_usage_patterns`, `config/style_profiles/<profile-name>.json` | 작성자 문체와 이모티콘 사용 패턴 신호를 담는 로컬 JSON 데이터. 이름 있는 여러 프로필 지원 |
| 짤방 | `MemeAsset`, `MemeIndex`, `config/meme_index.json` | 글 흐름에 넣을 반응 이미지 후보와 사용 맥락 태그 |
| OGQ 이모티콘 | `Settings.ogq_artwork_id`, `Settings.ogq_name` | 세루리안 OGQ 삽입 위치를 초안에 표시하기 위한 설정 |
| 초안 ID | `draft_id_from_time()`, `Draft.id` | `draft-YYYYMMDD-HHMMSS` 형식의 로컬 초안 식별자 |
| 프로필 이름 | `StyleProfile.profile_name`, `validate_profile_name()` | 소문자·숫자·하이픈·밑줄 1-64자 슬러그. 파일명으로 사용 |
| profile-refresh 명령 | `profile_refresh_command()`, `refresh_style_profile()`, `blog_scraper.service.scrape()` | 로컬 샘플 파일이나 HTTP/HTTPS 블로그·포스트 URL에서 문체를 추출해 named profile JSON을 저장 |
| 포스트 문서 | `PostDocument`, `TextBlock`, `ImageBlock`, `EmoticonBlock` | 스크래핑한 글을 텍스트·이미지·이모티콘 순서가 보존된 블록 목록으로 표현 |
| 구조화 샘플 텍스트 | `PostDocument.to_structured_text()` | URL 스크래핑 결과를 `[이미지]`, `[이모티콘:설명]` 마커가 포함된 문체 학습 입력으로 변환 |
| 이모티콘 마커 | `{{이모티콘:감정유형}}`, `PostGenerator.generate()` | 초안 본문에서 향후 발행 단계가 실제 OGQ 스티커로 치환할 이모티콘 삽입 의도 표시 |

| 예시 포스트 | `ExamplePost`, `FewShotRepository`, `style_profiler/examples.py`, `config/style_profiles/<name>-examples.json` | `profile-refresh` 시 스크래핑한 실제 포스트 원문(최대 3개). `draft` 시 few-shot으로 Claude에 주입해 문체 재현 품질 향상 |
| 짤방 등록 | `meme_add_command()`, `tag_meme_image()`, `add_or_update_meme()`, `MemeAsset` | `meme-add <파일>` 또는 `meme-fetch <URL>` 명령으로 이미지를 `assets/memes/`에 저장하고 Claude Vision으로 tags·use_cases 자동 생성. Claude Code 백엔드는 `--image` 옵션이 없으므로 프롬프트에 이미지 절대경로를 임베드해 CLI가 Read 도구로 분석 |
| 짤방 검색 | `meme_fetch_command()` | `meme-fetch <URL>` 명령으로 URL에서 이미지를 다운로드해 짤방 라이브러리에 등록 |
| 문맥 기반 짤방 배치 | `PostGenerator._place_memes_in_draft()` | 메모 키워드 단순 매칭 대신 생성된 초안 전체를 Claude가 분석해 각 문단에 적합한 `[짤방: id]` 마커 삽입 |
| 브라우저 미리보기 | `preview_command()`, `Draft.to_html()` | `preview` 명령이 생성하는 로컬 HTML 파일. 자동으로 브라우저가 열리고 네이버 블로그 유사 레이아웃으로 렌더링 |
| 클립보드 복사 | `preview_command()` + `pyperclip` | `preview` 실행 시 붙여넣기용 텍스트를 클립보드에 자동 복사. 네이버 SmartEditor에 수동 붙여넣기 위해 사용 |
| 붙여넣기용 텍스트 | `Draft.to_paste_text()`, `preview_command()`, `drafts/<draft_id>.txt` | 초안 마커(`[사진:]`/`[짤방:]`/`{{이모티콘:}}`)를 사람이 읽을 삽입 단서로 변환한 SmartEditor 붙여넣기용 plain text. preview가 클립보드 복사 + `.txt` 저장으로 제공. 사진은 basename만(절대경로 누출 0), 짤방 id→label은 cli가 meme tags/alt_text로 구성(ADR-007 디커플링 유지) |

| 포스트 목록 수집 | `naver.collect_blog_post_urls()`, `_select_post_hrefs()` | 블로그 홈/카테고리 페이지에서 최근 포스트 URL을 모으는 단계. 네이버는 JS 렌더 후 live DOM(`page.eval_on_selector_all`)에서 앵커를 추출해야 함 — 정적 HTML 커스텀 파서는 0개 반환 |
| 카테고리별 프로필 | `naver.category_list_api_url()`, `_select_post_urls_from_titlelist()`, `categoryNo` | 네이버 블로그 카테고리별로 글만 학습해 별도 named 프로필로 저장. `profile-refresh <카테고리URL> --profile <이름>`. categoryNo 필터는 모바일 홈/PostList가 무시하므로 `PostTitleListAsync.naver` JSON API로 처리 |

## Identical-Looking, Different Meaning

(같은 단어인데 컨텍스트마다 의미가 다른 경우. 예: price vs amount)
