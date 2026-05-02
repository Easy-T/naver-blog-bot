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
Last updated: 2026-05-02
