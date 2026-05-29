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

| 예시 포스트 | `style_profiler/examples.py` (예정), `config/style_profiles/<name>-examples.json` | `profile-refresh` 시 스크래핑한 실제 포스트 원문(최대 3개). `draft` 시 few-shot으로 Claude에 주입해 문체 재현 품질 향상 |
| 짤방 등록 | `meme_add_command()` (예정), `MemeAsset` | `meme-add <URL-또는-파일>` 명령으로 이미지를 `assets/memes/`에 저장하고 Claude Vision으로 tags·use_cases 자동 생성 |
| 짤방 검색 | `MemeSearchService` (예정) | `draft` 생성 중 `claude -p` 웹서치로 인터넷에서 문맥에 맞는 후보 이미지 URL 검색. 별도 이미지 API 키 불필요 |
| 문맥 기반 짤방 배치 | `MemeIndex.candidates_for_draft()` (예정) | 메모 키워드 단순 매칭(`candidates_for_memo`) 대신 생성된 초안 전체를 Claude가 분석해 각 문단에 적합한 짤방 배치 |
| 브라우저 미리보기 | `preview_command()` (갱신 예정) | `preview` 명령이 생성하는 로컬 HTML 파일. 자동으로 브라우저가 열리고 네이버 블로그 유사 레이아웃으로 렌더링 |
| 클립보드 복사 | `copy_command()` (예정) | 초안 내용을 클립보드에 복사. 네이버 SmartEditor에 수동 붙여넣기 위해 사용 |

## Identical-Looking, Different Meaning

(같은 단어인데 컨텍스트마다 의미가 다른 경우. 예: price vs amount)
