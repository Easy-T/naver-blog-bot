# Doctor Hardening Design

Created: 2026-05-03
Project: naver-blog-bot
Scope: Global Claude doctor preflight hardening before continuing to naver-blog-bot implementation planning

## Context

During `init-ai-ready-project`, two setup failures appeared before the project plan could proceed:

1. `jq` was missing in the WSL Ubuntu environment.
2. Claude home path resolution was confused between the WSL project home and the actual Windows Claude home.

The actual Claude home for this session is `C:\Users\12132\.claude`, reachable from Git Bash as `/c/Users/12132/.claude` and from WSL as `/mnt/c/Users/12132/.claude`.

A related non-obvious pattern is recorded in `docs/ai-context/non-obvious.md`: WSL working directory에서 `~/.claude` 경로 추론 오류.

## Goal

Strengthen the global `doctor.sh` preflight so future init/bootstrap work cannot silently continue after missing required tools or an incorrect Claude home path assumption.

## Selected Approach

Use the minimal global hardening approach:

- Modify `C:\Users\12132\.claude\setup\doctor.sh` directly.
- Keep the project repository as the place where the rationale and design are recorded.
- Avoid broad refactoring of `doctor.sh` before the main project plan.

## Required Behavior

### Required tools are hard gates

The following must be treated as hard failures when unavailable or broken:

- `claude`
- `node`
- `bash`
- `git`
- `jq`
- node JSON parsing
- writable Claude home

`jq` may still be auto-installed where supported, but if it remains unavailable after auto-install, doctor must report FAIL and exit non-zero.

### Optional tools remain warnings

The following should remain warnings:

- `gh` CLI missing
- `gh` unauthenticated, if checked
- internet connectivity failure
- Python missing
- low disk, unless a later rule explicitly changes this
- Claude home not git-managed

### Windows + WSL path awareness

When running in WSL, doctor should detect the WSL environment and check the Windows Claude home candidate:

- `/mnt/c/Users/12132/.claude`

If that candidate exists and `$HOME/.claude` points elsewhere, doctor should report the mismatch clearly instead of allowing `~/.claude` to be interpreted as `/home/<wsl-user>/.claude`.

The accepted runtime pattern is:

```bash
HOME=/mnt/c/Users/12132 bash ~/.claude/setup/doctor.sh
```

Doctor should make this expectation visible when it detects a WSL namespace mismatch.

### Existing backup edge case remains fixed

Backup rotation must not fail when no `.claude.backup-*` directories exist. The `ls` glob should be guarded so `set -euo pipefail` does not terminate the script early.

## Verification

After implementation, run doctor from WSL with the Windows Claude home explicitly set:

```bash
wsl.exe -d Ubuntu-24.04 -- bash -lc "export HOME=/mnt/c/Users/12132; cd /home/indietogo/projects/naver-blog-bot && bash ~/.claude/setup/doctor.sh"
```

Success criteria:

- command exits 0
- summary contains `FAIL=0`
- `jq installed` is PASS
- no premature exit during backup rotation
- path-related output makes the actual Claude home unambiguous

## Out of Scope

- Full rewrite of `doctor.sh`
- Adding a new installer framework
- Changing project source code
- Starting the naver-blog-bot implementation plan before this preflight hardening is verified
- Committing plugin metadata changes from the global `.claude` repository

## Self-Review

- Placeholder scan: no placeholders remain.
- Consistency check: selected approach matches the user-approved option 1, global direct hardening.
- Scope check: limited to doctor preflight behavior and documentation; no main project implementation included.
- Ambiguity check: hard fail and warn categories are explicitly listed.
