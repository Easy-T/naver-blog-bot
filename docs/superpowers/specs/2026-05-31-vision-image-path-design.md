# Claude Code Vision via Prompt Image Path — Design Spec

Created: 2026-05-31
Project: naver-blog-bot
RPI-Cycle: 9

## 1. Problem

`meme-add` / `meme-fetch` / `meme-build`가 실패한다:
```
Claude Code CLI failed. Detail: error: unknown option '--image'
```

`ClaudeCodeTextClient.complete_vision`이 `claude -p --image <path>`를 호출하는데, 설치된 Claude Code CLI(2.1.158)에는 `--image` 옵션이 **없다**. cycle 6에서 mock 테스트만 통과시키고 실제 CLI 옵션을 검증하지 않은 것이 원인.

**probe로 확정한 올바른 방법 (검증 완료):**
프롬프트(stdin)에 이미지의 **절대경로**를 적어주면 Claude Code가 자체 Read 도구로 이미지를 읽어 분석한다. probe에서 `sim/meme_smile.png` 절대경로를 프롬프트에 넣으니 "노란색 웃는 얼굴 스마일"로 정확히 분석함.

## 2. Goal

1. `ClaudeCodeTextClient.complete_vision`이 `--image` 없이, 프롬프트에 절대경로를 임베드해 동작한다.
2. `meme-add`로 실제 이미지가 태깅·등록된다.
3. SDK 백엔드(`ClaudeTextClient.complete_vision`, base64)는 변경 없음.

## 3. Approach

`ClaudeCodeTextClient.complete_vision` 변경:
- `args`에서 `--image`, `str(image_path)` 제거.
- 프롬프트를 `f"{prompt}\n\n분석할 이미지 파일 경로: {Path(image_path).resolve()}"`로 구성해 stdin(input)으로 전달.
- 나머지(에러 처리, `_parse_output`)는 그대로.

## 4. Out of Scope

- SDK 백엔드 vision (이미 base64로 정상).
- meme 명령 자체 로직, 본문 파서.

## 5. Files

| 파일 | 변경 |
|------|------|
| `src/naver_blog_bot/shared/claude_client.py` | `ClaudeCodeTextClient.complete_vision` — `--image` 제거, 절대경로 프롬프트 임베드 |
| `tests/unit/test_claude_client.py` | `test_claude_code_vision_client_builds_correct_args` 갱신: `--image` 미포함 + 절대경로가 input에 포함 |

## 6. Success Criteria

- 단위 테스트: args에 `--image` 없음, 절대경로가 stdin input에 포함.
- 전체 테스트 그린 + ruff.
- (수동) `meme-add sim/meme_smile.png`가 tags/use_cases와 함께 등록 성공.

## 7. Self-Review

- Placeholder 없음. 범위: claude_client.py + 테스트만. SDK 경로·meme 로직 불변.
