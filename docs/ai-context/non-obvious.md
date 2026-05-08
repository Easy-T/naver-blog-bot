# Non-Obvious Patterns — naver-blog-bot

> AI/사람의 잘못된 추론·해석은 여기 적지 않습니다.
> 시스템·프로세스·도구의 결함이 root cause인 항목만 누적.
> 등록 전 review-strict 5 Whys 통과 필수.
>
> 형식:
> ## YYYY-MM-DD: <한 줄 제목>
> - 증상: <관찰 내용>
> - 트리거: <활성화 행동>
> - Root cause: <시스템/프로세스 단위>
> - Action: <SMART, 가능하면 자동화 fitness function>
> - 재발 카운터: 0 (재발 시 +1)

## Active Patterns

## 2026-05-03: WSL Git HTTPS push hangs due to Windows GCM IPC stall
- 증상: WSL에서 `git push https://github.com/...` 실행 시 무한 대기하거나 `GIT_TERMINAL_PROMPT=0` 설정 시 "could not read Username: terminal prompts disabled" 오류로 즉시 실패. Windows Git으로 `safe.directory` 우회 후 즉시 성공.
- 트리거: Claude Code Bash 도구 또는 WSL 셸에서 HTTPS 원격으로 push 실행
- Root cause: WSL 2 샌드박스에서 Windows Git Credential Manager(GCM) IPC 소켓이 네트워크 중단 후 응답 없이 블로킹됨. Git의 credential helper 호출에 타임아웃이 없고, 프로젝트 설정에 WSL용 credential helper 우회 경로가 명시되지 않음.
- Action: `docs/ai-context/runbook.md`에 "WSL에서 push 시 `/mnt/c/Program\ Files/Git/bin/git.exe -c safe.directory=<repo> push` 사용" 항목 추가. `doctor.sh`에 WSL Git의 credential.helper 경로가 Windows GCM 바이너리인지 검사하고 경고하는 fitness check 추가 (스프린트 내 완료).
- 재발 카운터: 2

## 2026-05-08: Windows Git이 WSL UNC 경로에서 git worktree remove 실패
- 증상: `git worktree remove --force "//wsl.localhost/..."` 실행 시 "Function not implemented" 오류로 실패. WSL 네이티브 git에서 동일 경로를 상대 경로로 실행하면 성공.
- 트리거: Windows shell에서 Windows Git으로 WSL UNC 경로의 worktree를 제거할 때
- Root cause: Windows Git의 `rmdir` 구현이 `//wsl.localhost/` 마운트 경로에 대한 디렉터리 삭제 syscall을 지원하지 않음. WSL UNC 경로는 네트워크 드라이브로 인식되어 일부 파일 시스템 연산이 차단됨.
- Action: worktree 제거는 항상 WSL 네이티브 git(`wsl -d Ubuntu-24.04 -- git worktree remove`) 또는 `wsl -- rm -rf`로 실행. Windows Git은 UNC 경로 worktree 삭제에 사용하지 않는다.
- 재발 카운터: 0

## 2026-05-08: WSL 설치 uv가 Windows shell PATH에 없음
- 증상: Bash 도구(Windows shell)에서 `uv run` 실행 시 "command not found". `wsl -d Ubuntu-24.04 -- bash -c "uv run ..."` 에서도 동일 오류. 전체 경로 `/home/indietogo/.local/bin/uv`로 실행 시 성공.
- 트리거: Windows shell에서 WSL 내 uv를 호출하거나, WSL bash에서 non-login/non-interactive 셸로 실행할 때
- Root cause: uv가 `~/.local/bin`에 설치되어 있고, 이 경로는 WSL 로그인 셸의 PATH에만 포함됨. `wsl -- bash -c "..."` 는 non-interactive 셸이라 `.profile`/`.bashrc`가 로드되지 않아 PATH가 축소됨.
- Action: WSL uv 호출 시 항상 `/home/indietogo/.local/bin/uv` 전체 경로 사용. runbook에 "WSL 명령은 non-interactive bash임을 전제하고 전체 경로로 실행" 항목 추가.
- 재발 카운터: 0

## 2026-05-02: WSL working directory에서 ~/.claude 경로 추론 오류
- 증상: Claude Code가 WSL UNC 경로를 working directory로 표시할 때 `~/.claude`를 `/home/<wsl-user>/.claude`로 잘못 매핑
- 트리거: WSL 경로 프로젝트에서 글로벌 Claude 설정·skill·setup 경로 참조
- Root cause: Claude Code 세션 컨텍스트 포맷이 프로젝트 working directory만 제공하고 Windows 글로벌 Claude 홈 경로를 별도 필드로 노출하지 않음
- Action: Windows+WSL 혼합 환경에서 `~/.claude`를 참조하기 전 `HOME`과 실제 Claude 홈 경로를 확인하고, WSL 명령에는 필요 시 `HOME=/mnt/c/Users/12132`를 명시한다
- 재발 카운터: 0

## High Priority (재발 ≥ 2회)

(없음)

## Archive (해결 또는 휴면 패턴)

(없음 — active ≥30 또는 줄 수 ≥100 시 가장 오래된 비재발 항목 5개 자동 이동)

---
Last updated: 2026-05-08
