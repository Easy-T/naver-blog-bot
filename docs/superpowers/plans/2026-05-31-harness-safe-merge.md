# Harness Safe Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize only the tracked permission bits required by the harness while preserving project history, scaffold/context files, and existing working-tree content.

**Architecture:** This is a permission-only safe merge. Implementation must use Git index and filesystem mode operations (`git update-index --chmod=...`, `chmod ...`) and must not edit file contents, regenerate scaffold files, overwrite local changes, commit, push, tag, or run release actions.

**Tech Stack:** Git index metadata, filesystem executable bits, Bash verification, Python JSON parsing for `.claude/state.json`.

---

## File Structure

- Modify mode only: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/scripts/check.sh` -> tracked mode `100755`.
- Modify mode only if already tracked: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/.claude/hooks/pre-commit-deny.sh` -> tracked mode `100755`.
- Modify mode only: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/.github/workflows/ci.yml` -> tracked mode `100644`.
- Preserve without content edits: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/docs/ai-context`, `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/CONTEXT.md`, `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/CLAUDE.md`, `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/.claude/state.json`.
- Do not create, modify, or delete any other files.

## Tasks

### Task 1: Capture baseline state before changes

**Files:**
- Read/verify only: repository working tree and preserved context/state paths.

- [ ] **Step 1: Move to the repository root for all commands**

Run:

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
```

Expected: command succeeds with no output.

- [ ] **Step 2: Record pre-existing working-tree changes**

Run:

```bash
git status --short
git diff --stat
git diff --summary
```

Expected: any pre-existing changes are recorded before implementation. Do not overwrite or discard them.

- [ ] **Step 3: Record baseline tracked modes**

Run:

```bash
git ls-files -s -- scripts/check.sh .github/workflows/ci.yml
if git ls-files --error-unmatch .claude/hooks/pre-commit-deny.sh >/dev/null 2>&1; then
  git ls-files -s -- .claude/hooks/pre-commit-deny.sh
else
  printf 'SKIP: .claude/hooks/pre-commit-deny.sh is not tracked\n'
fi
```

Expected: `scripts/check.sh` and `.github/workflows/ci.yml` are tracked. The hook is either tracked and printed, or explicitly skipped because it is not tracked.

- [ ] **Step 4: Record baseline cycle state**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path
state = json.loads(Path('.claude/state.json').read_text(encoding='utf-8'))
cycle = state.get('cycle', {})
print(f"count={cycle.get('count')}")
print(f"last_cycle_id={cycle.get('last_cycle_id')}")
PY
```

Expected: record the exact `count` and `last_cycle_id` values; both must be identical after implementation.

### Task 2: Apply mode-only normalization through Git

**Files:**
- Modify mode only: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/scripts/check.sh`.
- Modify mode only if already tracked: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/.claude/hooks/pre-commit-deny.sh`.
- Modify mode only: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/.github/workflows/ci.yml`.

- [ ] **Step 1: Make `scripts/check.sh` executable in the Git index**

Run:

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
git update-index --chmod=+x scripts/check.sh
chmod +x scripts/check.sh
```

Expected: command succeeds with no output. Git index and filesystem mode are executable. No file content is edited.

- [ ] **Step 2: Make the pre-commit deny hook executable only if tracked**

Run:

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
if git ls-files --error-unmatch .claude/hooks/pre-commit-deny.sh >/dev/null 2>&1; then
  git update-index --chmod=+x .claude/hooks/pre-commit-deny.sh
  chmod +x .claude/hooks/pre-commit-deny.sh
  printf 'UPDATED: .claude/hooks/pre-commit-deny.sh mode set executable\n'
else
  printf 'SKIP: .claude/hooks/pre-commit-deny.sh is not tracked\n'
fi
```

Expected: tracked hook mode is updated to executable in the Git index and filesystem, or the hook is skipped without creating a new file.

- [ ] **Step 3: Ensure workflow YAML is non-executable in the Git index**

Run:

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
git update-index --chmod=-x .github/workflows/ci.yml
chmod -x .github/workflows/ci.yml
```

Expected: command succeeds with no output. Git index and filesystem mode are non-executable. No workflow content is edited.

### Task 3: Verify mode-only footprint and preserved context

**Files:**
- Verify: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/scripts/check.sh`.
- Verify: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/.claude/hooks/pre-commit-deny.sh` if tracked.
- Verify: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/.github/workflows/ci.yml`.
- Verify preserved paths: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/docs/ai-context`, `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/CONTEXT.md`, `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/CLAUDE.md`, `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/.claude/state.json`.

- [ ] **Step 1: Inspect changed-file footprint**

Run:

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
git status --short
git diff --stat
git diff --summary
```

Expected: implementation-caused changes are mode-only for the scoped files. There are no content diffs from this task and no new scaffold/context overwrites.

- [ ] **Step 2: Confirm final tracked modes**

Run:

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
git ls-files -s -- scripts/check.sh .github/workflows/ci.yml
if git ls-files --error-unmatch .claude/hooks/pre-commit-deny.sh >/dev/null 2>&1; then
  git ls-files -s -- .claude/hooks/pre-commit-deny.sh
else
  printf 'SKIP: .claude/hooks/pre-commit-deny.sh is not tracked\n'
fi
```

Expected:
- `scripts/check.sh` prints mode `100755`.
- `.github/workflows/ci.yml` prints mode `100644`.
- `.claude/hooks/pre-commit-deny.sh` prints mode `100755` if tracked, otherwise the skip message prints.

- [ ] **Step 3: Confirm cycle state is preserved**

Run:

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
python - <<'PY'
import json
from pathlib import Path
state = json.loads(Path('.claude/state.json').read_text(encoding='utf-8'))
cycle = state.get('cycle', {})
print(f"count={cycle.get('count')}")
print(f"last_cycle_id={cycle.get('last_cycle_id')}")
PY
```

Expected: `count` and `last_cycle_id` exactly match the values recorded in Task 1.

- [ ] **Step 4: Confirm preserved context paths still exist**

Run:

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
python - <<'PY'
from pathlib import Path
for raw in ['docs/ai-context', 'CONTEXT.md', 'CLAUDE.md', '.claude/state.json']:
    path = Path(raw)
    print(f"{raw}: {'OK' if path.exists() else 'MISSING'}")
PY
```

Expected: every line ends with `OK`.

- [ ] **Step 5: Scan preserved context for obvious scaffold reset markers**

Run:

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
python - <<'PY'
from pathlib import Path
terms = ['TODO', 'TBD', 'PLACEHOLDER', 'your-project', 'example.com', 'lorem ipsum']
paths = [Path('CONTEXT.md'), Path('CLAUDE.md')]
paths.extend(p for p in Path('docs/ai-context').rglob('*') if p.is_file())
matches = []
for path in paths:
    text = path.read_text(encoding='utf-8', errors='replace')
    lower = text.lower()
    for term in terms:
        if term.lower() in lower:
            matches.append((str(path), term))
if matches:
    for path, term in matches:
        print(f"MARKER: {path}: {term}")
else:
    print('No scaffold/template reset markers found')
PY
```

Expected: `No scaffold/template reset markers found`. If markers appear, report them as verification evidence and do not edit context files in this task.

### Task 4: Run permission-appropriate verification commands

**Files:**
- Verify shell syntax: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/scripts/check.sh`.
- Verify shell syntax if touched/tracked: `//wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot/.claude/hooks/pre-commit-deny.sh`.

- [ ] **Step 1: Syntax-check changed shell scripts**

Run:

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
bash -n scripts/check.sh
if git ls-files --error-unmatch .claude/hooks/pre-commit-deny.sh >/dev/null 2>&1; then
  bash -n .claude/hooks/pre-commit-deny.sh
else
  printf 'SKIP: .claude/hooks/pre-commit-deny.sh is not tracked\n'
fi
```

Expected: `bash -n` exits `0` for every checked script. If syntax fails, stop and report the blocker rather than editing script contents.

- [ ] **Step 2: Run local check only when prerequisites are available**

Run:

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
if command -v uv >/dev/null 2>&1; then
  ./scripts/check.sh
else
  printf 'SKIP: uv is not available in this environment\n'
fi
```

Expected: if `uv` exists, `./scripts/check.sh` exits `0`. If skipped, report `uv is not available in this environment` as the explicit skip reason.

- [ ] **Step 3: Final no-content-edit confirmation**

Run:

```bash
cd //wsl$/Ubuntu-24.04/home/indietogo/projects/naver-blog-bot
git diff --summary
git diff -- . ':!scripts/check.sh' ':!.claude/hooks/pre-commit-deny.sh' ':!.github/workflows/ci.yml'
```

Expected: `git diff --summary` shows only intended mode changes for scoped files, accounting for any pre-existing changes recorded in Task 1. The path-limited content diff emits no implementation-caused scaffold/context content changes.

## Completion Criteria

- Modes are verified as `scripts/check.sh` -> `100755`, `.github/workflows/ci.yml` -> `100644`, and `.claude/hooks/pre-commit-deny.sh` -> `100755` only if already tracked.
- `.claude/state.json` still parses as JSON, and `count`/`last_cycle_id` match the Task 1 baseline.
- `docs/ai-context`, `CONTEXT.md`, `CLAUDE.md`, and `.claude/state.json` still exist and were not overwritten.
- Placeholder scan result is reported.
- `bash -n` results are reported for every touched shell script.
- Local check result is reported, or the exact prerequisite/environment skip reason is reported.
- No commits, pushes, tags, release actions, scaffold regeneration, content edits, or unrelated cleanup are performed.
