# Domain Glossary — naver-blog-bot

> 사내 용어 ↔ 코드 식별자 매핑. AI가 도메인 언어를 정확히 사용하도록.
> 새 용어 등장 시 메인이 confidence < 80%면 사용자에게 확인 후 자동 추가.

## Domain → Code

| 도메인 용어 | 코드 식별자 | 비고 |
|---|---|---|
| 체험단 후기 | `Draft`, `PostGenerator.generate()` | 사진과 메모를 바탕으로 생성하는 리뷰형 네이버 블로그 초안 |
| 스타일 프로필 | `StyleProfile`, `config/style_profiles/<profile-name>.json` | 작성자 문체 신호를 담는 로컬 JSON 데이터. 이름 있는 여러 프로필 지원 |
| 짤방 | `MemeAsset`, `MemeIndex`, `config/meme_index.json` | 글 흐름에 넣을 반응 이미지 후보와 사용 맥락 태그 |
| OGQ 이모티콘 | `Settings.ogq_artwork_id`, `Settings.ogq_name` | 세루리안 OGQ 삽입 위치를 초안에 표시하기 위한 설정 |
| 초안 ID | `draft_id_from_time()`, `Draft.id` | `draft-YYYYMMDD-HHMMSS` 형식의 로컬 초안 식별자 |
| 프로필 이름 | `StyleProfile.profile_name`, `validate_profile_name()` | 소문자·숫자·하이픈·밑줄 1-64자 슬러그. 파일명으로 사용 |
| profile-refresh 명령 | `profile_refresh_command()`, `refresh_style_profile()`, `blog_scraper.service.scrape()` | 로컬 샘플 파일이나 HTTP/HTTPS 블로그·포스트 URL에서 문체를 추출해 named profile JSON을 저장 |
| 포스트 문서 | `PostDocument`, `TextBlock`, `ImageBlock`, `EmoticonBlock` | 스크래핑한 글을 텍스트·이미지·이모티콘 순서가 보존된 블록 목록으로 표현 |
| 구조화 샘플 텍스트 | `PostDocument.to_structured_text()` | URL 스크래핑 결과를 `[이미지]`, `[이모티콘:설명]` 마커가 포함된 문체 학습 입력으로 변환 |

## Identical-Looking, Different Meaning

(같은 단어인데 컨텍스트마다 의미가 다른 경우. 예: price vs amount)
