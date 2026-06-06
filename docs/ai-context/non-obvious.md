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

## 2026-06-07: WSL 경계가 종료한 git 인덱스 쓰기가 0-byte stale `.git/index.lock`를 남겨 후속 커밋 차단
- 증상: WSL 경계(Bash 도구 → `wsl … git`)로 `git add`/`git commit` 실행 시 간헐적으로 `fatal: Unable to create '.../.git/index.lock': File exists.` (Exit 128)로 실패. 발생 시 항상 (a) live git 프로세스 없음(`pgrep -x git` 무반응), (b) 남은 lock이 **0 byte**. `rm -f .git/index.lock` 후 재시도하면 즉시 성공. cycle 13(2회)·cycle 14(1회) — 3사이클 연속 재발.
- 트리거: WSL2에서 win32→WSL 경계를 넘는 인덱스 쓰기 git 명령(add/commit). 경계의 Bash-도구 타임아웃·하네스의 `git status` 스냅샷·읽기전용 서브에이전트(explore/review-strict)의 git read가 lock을 짧게 점유/경합하다 조기 종료될 때.
- Root cause: git의 index.lock은 TTL·stale 자동복구가 없음 — 경계가 인덱스 쓰기 git을 "빈 lock 생성(`O_CREAT|O_EXCL`) 직후 ~ 내용 기록 전" 창에서 종료하면 0-byte orphan lock이 남아 이후 모든 인덱스 쓰기를 영구 차단. 여기에 워크플로에 **git-쓰기 전 stale-lock 가드가 없음**이 겹쳐 매번 수동 `rm -f`를 요구. (시스템: git no-TTL lock + WSL 경계 조기 종료 / 프로세스: 가드 부재. 하네스/경계가 유발한 중단은 시스템 사실 — AI 부주의 아님. review-strict 5 Whys PASS.)
- Action (SMART): `scripts/git-commit.sh` 가드 헬퍼 추가(완료, 2026-06-07) — 커밋 전 `[ -e .git/index.lock ] && ! pgrep -x git` 일 때만 stale lock 제거 후 `git add -A` + `git commit`. 사이클 커밋에 사용, runbook "Commit (WSL stale index.lock guard)"에 문서화. Fitness: 재발 카운터로 추적, cycle 15~17 동안 index.lock 실패 0이면 성공. (deny 패턴/`--no-verify` 미사용, PreToolUse deny 훅 우회 없음.)
- 재발 카운터: 0

## High Priority (재발 ≥ 2회)

(없음)

## Archive (해결 또는 휴면 패턴)

(없음 — active ≥30 또는 줄 수 ≥100 시 가장 오래된 비재발 항목 5개 자동 이동)

---
Last updated: 2026-05-08

---

## NOBV-002: 검증 게이트의 `&&` 체인이 false-green을 만든다

- **발생**: cli.py/models.py 변경 후 `bash scripts/check.sh`가 RC 0("== check complete ==")을 냈지만, 실제로는 ruff format 실패로 **pytest가 실행조차 안 됐고** 전체 스위트엔 1개 실패 + 신규 기능 테스트 0개가 숨어 있었다. closeout review-strict가 적발.
- **근인 (5 Whys)**:
  1. 왜 false-green? → check.sh가 RC 0을 반환했지만 pytest는 돌지 않았다.
  2. 왜 pytest가 안 돌았나? → `ruff check && ruff format --check && pytest` 한 줄에서 format이 실패해 단락(short-circuit)됐다.
  3. 왜 단락이 스크립트를 멈추지 않았나? → `set -e`는 `&&` 리스트의 **마지막이 아닌** 명령 실패에는 종료하지 않는다(bash 사양).
  4. 왜 그렇게 작성됐나? → 한 줄 `&&` 체인이 간결해 보였고 단계 분리의 필요가 인지되지 않았다.
  5. (시스템 근본) 왜 게이트 자체의 정확성이 검증되지 않았나? → "게이트가 실패를 실제로 잡는가"를 확인하는 메타 점검 관행이 없었다.
- **교훈**: 검증 게이트는 각 명령을 개별 문장으로 두어 `set -e`가 모든 실패를 잡게 한다. green일 때도 단계별 출력(특히 "N passed")을 눈으로 확인한다. 함께 드러난 자매 패턴 — 단위 테스트가 placeholder 문자열만 단언해 실제 이미지 렌더링 커버리지가 0이었음 → 기능 추가 시 TDD(실패 테스트 선작성)를 건너뛰지 않는다.
- **Action (SMART)**: scripts/check.sh를 단계별 개별 명령 + 단계 echo로 분리(완료, cycle 11). 이후 closeout 시 pytest 단계의 "passed" 토큰을 명시적으로 확인한다.
