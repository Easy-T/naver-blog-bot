**Status:** completed
**RPI-Cycle:** 1
**Started:** 2026-05-03

# Doctor Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Harden the global Claude `doctor.sh` preflight so missing required tools and Windows+WSL Claude home path mismatches cannot be silently skipped during project init.

**Architecture:** This is a surgical update to the global shell script `C:\Users\12132\.claude\setup\doctor.sh`. The project repository stores the approved design and this implementation plan; the actual runtime behavior lives in the global Claude setup script.

**Tech Stack:** Bash, WSL Ubuntu, Windows-hosted Claude home at `/mnt/c/Users/12132/.claude`, Git for verification.

---

## File Structure

- Modify: `/c/Users/12132/.claude/setup/doctor.sh`
  - Responsibility: global Claude preflight checks for tools, writable Claude home, WSL path awareness, and bootstrap readiness.
- Reference: `/home/indietogo/projects/naver-blog-bot/docs/superpowers/specs/2026-05-03-doctor-hardening-design.md`
  - Responsibility: approved design and success criteria.
- Reference: `/home/indietogo/projects/naver-blog-bot/docs/ai-context/non-obvious.md`
  - Responsibility: root-caused WSL `~/.claude` path confusion pattern.

---

### Task 1: Add WSL Claude Home Detection

**Files:**
- Modify: `/c/Users/12132/.claude/setup/doctor.sh`

- [x] **Step 1: Inspect the current script section around initialization**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('/c/Users/12132/.claude/setup/doctor.sh')
for i, line in enumerate(p.read_text().splitlines(), start=1):
    if 1 <= i <= 25:
        print(f'{i}\t{line}')
PY
```

Expected: output shows `set -euo pipefail`, `PASS=0`, `FAIL=0`, `WARN=0`, `ITEMS=()`, and the `check()` function.

- [x] **Step 2: Add helper variables after `ITEMS=()`**

Insert this block immediately after `ITEMS=()`:

```bash
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
WINDOWS_CLAUDE_HOME_CANDIDATE="/mnt/c/Users/12132/.claude"
IS_WSL=0
if [ -r /proc/version ] && grep -qiE 'microsoft|wsl' /proc/version; then
  IS_WSL=1
fi
```

- [x] **Step 3: Verify the inserted block exists exactly once**

Run:

```bash
grep -nE 'CLAUDE_HOME=|WINDOWS_CLAUDE_HOME_CANDIDATE=|IS_WSL=' /c/Users/12132/.claude/setup/doctor.sh
```

Expected: one occurrence each for `CLAUDE_HOME=`, `WINDOWS_CLAUDE_HOME_CANDIDATE=`, and initial `IS_WSL=0`, plus the assignment inside the WSL detection `if`.

- [x] **Step 4: Commit is not required yet**

No commit at this task boundary because Task 2 depends on the helper variables and the global repo also has unrelated plugin metadata changes that must not be included.

---

### Task 2: Use `CLAUDE_HOME` for Claude Directory Checks

**Files:**
- Modify: `/c/Users/12132/.claude/setup/doctor.sh`

- [x] **Step 1: Replace direct `$HOME/.claude` checks with `$CLAUDE_HOME`**

Apply these exact replacements:

```text
$HOME/.claude/.write-test -> $CLAUDE_HOME/.write-test
$HOME/.claude/setup -> $CLAUDE_HOME/setup
$HOME/.claude/CLAUDE.md -> $CLAUDE_HOME/CLAUDE.md
$HOME/.claude.backup-$TODAY -> $CLAUDE_HOME.backup-$TODAY
$HOME/.claude/.git -> $CLAUDE_HOME/.git
$HOME/.claude -> $CLAUDE_HOME
$HOME/.claude.backup-* -> $CLAUDE_HOME.backup-*
```

The intended resulting code snippets are:

```bash
if touch "$CLAUDE_HOME/.write-test" 2>/dev/null && rm -f "$CLAUDE_HOME/.write-test"; then
```

```bash
mkdir -p "$CLAUDE_HOME/setup"
touch "$CLAUDE_HOME/setup/.installed"
```

```bash
CLAUDE_MD="$CLAUDE_HOME/CLAUDE.md"
```

```bash
BACKUP="$CLAUDE_HOME.backup-$TODAY"
if [ -d "$CLAUDE_HOME/.git" ]; then
  check "backup directory" "PASS" "skipped (~/.claude is git-managed)"
elif [ ! -d "$BACKUP" ]; then
  cp -r "$CLAUDE_HOME" "$BACKUP" 2>/dev/null && check "backup directory" "PASS" "$BACKUP" || check "backup directory" "WARN" "cp failed"
else
  check "backup directory" "PASS" "exists: $BACKUP"
fi
```

```bash
OLD_BACKUPS=$({ ls -dt "$CLAUDE_HOME".backup-* 2>/dev/null || true; } | tail -n +$((KEEP+1)))
```

```bash
if [ -d "$CLAUDE_HOME/.git" ]; then
```

- [x] **Step 2: Verify no mutable Claude-home checks still use `$HOME/.claude`**

Run:

```bash
grep -n '\$HOME/.claude' /c/Users/12132/.claude/setup/doctor.sh || true
```

Expected: no output, or only comments that do not affect runtime. If runtime code appears, replace it with `$CLAUDE_HOME`.

- [x] **Step 3: Run shell syntax check**

Run:

```bash
bash -n /c/Users/12132/.claude/setup/doctor.sh
```

Expected: exit 0 with no output.

---

### Task 3: Add WSL Namespace Mismatch Check

**Files:**
- Modify: `/c/Users/12132/.claude/setup/doctor.sh`

- [x] **Step 1: Add a reusable report function after `check()`**

Insert this block immediately after the `check()` function:

```bash
report_results() {
  echo
  echo "[doctor] Results:"
  for line in "${ITEMS[@]}"; do echo "  $line"; done
  echo
  echo "[doctor] PASS=$PASS  WARN=$WARN  FAIL=$FAIL"
}
```

- [x] **Step 2: Replace the bottom inline report with `report_results`**

Replace:

```bash
echo
echo "[doctor] Results:"
for line in "${ITEMS[@]}"; do echo "  $line"; done
echo
echo "[doctor] PASS=$PASS  WARN=$WARN  FAIL=$FAIL"
```

with:

```bash
report_results
```

- [x] **Step 3: Add the WSL path awareness check after OS detection**

Insert this block immediately after the `case "$(uname -s)" in ... esac` OS detection block. The immediate exit prevents doctor from creating `/home/<wsl-user>/.claude` after detecting a namespace mismatch.

```bash
if [ "$IS_WSL" -eq 1 ]; then
  check "WSL environment detected" "PASS" "$(uname -r)"
  if [ -d "$WINDOWS_CLAUDE_HOME_CANDIDATE" ]; then
    if [ "$CLAUDE_HOME" = "$WINDOWS_CLAUDE_HOME_CANDIDATE" ]; then
      check "Claude home namespace" "PASS" "$CLAUDE_HOME"
    else
      check "Claude home namespace" "FAIL" "WSL detected; run with HOME=/mnt/c/Users/12132 or CLAUDE_HOME=$WINDOWS_CLAUDE_HOME_CANDIDATE (current: $CLAUDE_HOME)"
      report_results
      echo "[doctor] FATAL: Claude home namespace mismatch." >&2
      exit 1
    fi
  else
    check "Windows Claude home candidate" "WARN" "$WINDOWS_CLAUDE_HOME_CANDIDATE not found"
  fi
fi
```

- [x] **Step 2: Verify the mismatch check is present**

Run:

```bash
grep -nE 'WSL environment detected|Claude home namespace|Windows Claude home candidate' /c/Users/12132/.claude/setup/doctor.sh
```

Expected: all three labels appear.

- [x] **Step 3: Run syntax check**

Run:

```bash
bash -n /c/Users/12132/.claude/setup/doctor.sh
```

Expected: exit 0 with no output.

---

### Task 4: Make `jq` Missing a Hard Failure

**Files:**
- Modify: `/c/Users/12132/.claude/setup/doctor.sh`

- [x] **Step 1: Change the post-auto-install `jq` fallback from WARN to FAIL**

Replace this code:

```bash
check "jq installed" "WARN" "auto-install failed — hooks use node, jq is optional"
```

with:

```bash
check "jq installed" "FAIL" "auto-install failed — required for bootstrap verification"
```

- [x] **Step 2: Verify the old optional message is gone**

Run:

```bash
grep -n 'hooks use node, jq is optional' /c/Users/12132/.claude/setup/doctor.sh || true
grep -n 'auto-install failed — required for bootstrap verification' /c/Users/12132/.claude/setup/doctor.sh
```

Expected: first command has no output; second command prints one matching line.

- [x] **Step 3: Run syntax check**

Run:

```bash
bash -n /c/Users/12132/.claude/setup/doctor.sh
```

Expected: exit 0 with no output.

---

### Task 5: Verify Doctor Behavior in WSL

**Files:**
- Modify: `/c/Users/12132/.claude/setup/doctor.sh`

- [x] **Step 1: Run doctor with explicit Windows Claude home**

Run:

```bash
wsl.exe -d Ubuntu-24.04 -- bash -lc "export HOME=/mnt/c/Users/12132; cd /home/indietogo/projects/naver-blog-bot && bash ~/.claude/setup/doctor.sh"
```

Expected:

```text
[doctor] PASS=<number>  WARN=<number>  FAIL=0
```

The output must include:

```text
✓ jq installed
✓ Claude home namespace — /mnt/c/Users/12132/.claude
✓ backup rotation
```

- [x] **Step 2: Run doctor without overriding WSL HOME to confirm mismatch is caught**

Run:

```bash
wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /home/indietogo/projects/naver-blog-bot && bash /mnt/c/Users/12132/.claude/setup/doctor.sh"; test $? -ne 0
```

Expected: command exits 0 overall because `test $? -ne 0` confirms doctor itself failed. Doctor output must include:

```text
✗ Claude home namespace
```

- [x] **Step 3: Confirm global diff only includes `setup/doctor.sh` plus unrelated plugin metadata remains unstaged**

Run:

```bash
git -C /c/Users/12132/.claude status --short
git -C /c/Users/12132/.claude diff -- setup/doctor.sh
```

Expected: `setup/doctor.sh` is modified. `plugins/installed_plugins.json` and `plugins/known_marketplaces.json` may also be modified but must not be staged or committed by this plan.

---

### Task 6: Commit Global Doctor Change Only If Requested

**Files:**
- Modify: `/c/Users/12132/.claude/setup/doctor.sh`

- [x] **Step 1: Ask before committing global repo changes**

Global `.claude` is a separate repository and may contain unrelated plugin metadata changes. Ask the user before committing the global doctor change.

Expected user-facing text:

```text
Global doctor hardening is verified. Do you want me to commit only setup/doctor.sh in C:\Users\12132\.claude now?
```

- [x] **Step 2: If approved, stage only `setup/doctor.sh`**

Run:

```bash
git -C /c/Users/12132/.claude add -- setup/doctor.sh
git -C /c/Users/12132/.claude diff --cached --stat
```

Expected: cached diff contains only `setup/doctor.sh`.

- [x] **Step 3: Commit with explicit message**

Run:

```bash
git -C /c/Users/12132/.claude commit -m "$(cat <<'EOF'
Harden doctor preflight for WSL setup

Require jq after auto-install attempts and detect Windows/WSL Claude home namespace mismatches before bootstrap work proceeds.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds and unrelated plugin metadata remains unstaged.

---

## Self-Review

- Spec coverage: The plan covers required hard gates, optional warnings, WSL path awareness, backup rotation safety, and WSL verification commands from the spec.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: Shell variables are consistently named `CLAUDE_HOME`, `WINDOWS_CLAUDE_HOME_CANDIDATE`, and `IS_WSL`.
- Scope check: The plan only modifies global `doctor.sh` and does not touch naver-blog-bot source implementation.
