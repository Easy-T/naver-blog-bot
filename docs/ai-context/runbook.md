# Runbook — naver-blog-bot

> ⚠️ 이 파일은 **운영·배포·장애 대응**의 기술적 실행 절차입니다.
> ⚠️ 프로젝트 작업 계획(Work Plan)은 `docs/superpowers/specs/` 와
>    `docs/superpowers/plans/`에 보관됩니다.
> ⚠️ 의사결정·전략은 ADR(`architecture.md`)에 보관됩니다.

## Local Quality Gate

```bash
bash scripts/check.sh
```

통과 기준: 명령이 exit code 0으로 종료되어야 함.

실패 시:
- 오류 메시지 확인 → 수정 후 재실행
- `scripts/check.sh`를 직접 열어 세부 명령 확인

---

## CI Gate

PR 생성 후 CI 통과 확인:

```bash
gh pr checks --watch --timeout 300
```

실패 시:
- `gh pr checks` 출력에서 실패 job 확인
- `gh run view <run-id> --log` 로 상세 로그 확인
- 수정 → push → 자동 재실행

---

## PR Creation

```bash
git push -u origin $(git rev-parse --abbrev-ref HEAD)
gh pr create --fill
```

PR body 기준:
- 구현 범위 요약 포함
- `docs/superpowers/plans/` 경로 참조
- 위험/rollback 방안 포함

---

## Pre-Merge Review

merge 전 review-strict subagent가 다음을 검증:
- local check 통과 증거
- PR description이 실제 diff와 일치
- active plan scope 충족 + scope creep 없음
- security/external-state 위험 없음
- 테스트 커버리지 (happy path + 실패 path)
- runbook/ADR/glossary drift 없음

결과: Critical / Important / Minor / Suggestions 분류

---

## Merge Policy

AI는 merge를 결정하지 않는다.

merge 조건 (모두 충족 시):
1. local check PASS
2. CI PASS
3. review-strict: Critical=0
4. 사용자 명시 승인

```bash
gh pr merge --squash --delete-branch
```

---

## Deploy
(아직 정의되지 않음)

## Rollback
(아직 정의되지 않음)

## Common Operations

### Install dependencies

```bash
uv sync --group dev
```

### Run tests

```bash
uv run pytest -v
```

### Initialize local state directories

```bash
uv run naver-bot init
```

### Generate a local draft

```bash
uv run naver-bot draft path/to/photo1.jpg path/to/photo2.jpg "제품 첫인상이 좋고 사진은 두 장"
```

### Preview a draft

```bash
uv run naver-bot preview draft-20260503-120000
```

## Health Checks / Dashboards
(아직 정의되지 않음)

## Incident Response (간단 — 자세한 건 별도 playbook으로 분리 권장)
(아직 정의되지 않음)
