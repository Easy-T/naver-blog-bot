# CONTEXT — naver-blog-bot

> 도메인 용어 사전. 구현 세부사항은 없음. AI가 도메인 언어를 정확히 쓰도록.
> 신규 용어 등장 시 confidence < 80% → 사용자 확인 후 추가.

## 용어 사전

| 용어 | 정의 |
|------|------|
| 체험단 후기 | 제품·서비스 체험 후 작성하는 네이버 블로그 리뷰 포스트. 이 도구의 1차 사용 목적. |
| 스타일 프로필 | 작성자 문체 특성을 JSON으로 저장한 파일. `config/style_profiles/<name>.json`. |
| 예시 포스트 | `profile-refresh` 시 스크래핑된 실제 포스트 원문(최대 3개). `config/style_profiles/<name>-examples.json`에 저장. `draft` 시 few-shot으로 Claude에 주입. |
| 짤방 | 블로그 본문 흐름에 삽입하는 반응 이미지. `assets/memes/`에 저장, `config/meme_index.json`으로 인덱싱. |
| 짤방 등록 | `meme-add <URL-또는-파일>` 명령으로 이미지를 `assets/memes/`에 저장하고 Claude Vision으로 태그 자동 생성. |
| 짤방 검색 | `draft` 생성 중 `claude -p` 웹서치로 인터넷에서 문맥에 맞는 후보 이미지 URL을 찾는 행위. 별도 이미지 API 키 불필요. |
| 문맥 기반 짤방 배치 | 메모 키워드 단순 매칭이 아닌, 생성된 초안 전체 내용을 Claude가 읽어 각 문단에 적합한 짤방을 배치하는 방식. |
| 브라우저 미리보기 | `preview` 명령이 생성하는 로컬 HTML 파일. 브라우저가 자동으로 열리고 네이버 블로그 유사 레이아웃으로 렌더링. |
| 클립보드 복사 | `preview` 또는 별도 명령으로 초안 내용을 클립보드에 복사. 네이버 SmartEditor에 붙여넣기 위해 사용. |
| OGQ 이모티콘 | 세루리안 세트(artworkId: `644e042a7d7f8`). 초안 본문에 `{{이모티콘:감정유형}}` 마커로 삽입 위치 표시. |
| 이모티콘 마커 | `{{이모티콘:감정유형}}` 형식. 발행 단계에서 사람이 실제 OGQ 스티커로 교체. |
| 초안 | Claude가 생성한 마크다운 블로그 글. `drafts/<draft_id>.json`에 저장. |
| profile-refresh | 블로그 URL 또는 로컬 파일에서 문체를 추출해 스타일 프로필 + 예시 포스트를 저장하는 명령. |

## 범위 결정 (Phase 1)

- `publish` 명령: **Phase 1 제외** — 사용자가 HTML 미리보기 후 네이버 SmartEditor에 수동 복붙.
- Naver 자동 포스팅: Phase 2 이후 검토 (봇 탐지 리스크로 우선순위 낮춤).
