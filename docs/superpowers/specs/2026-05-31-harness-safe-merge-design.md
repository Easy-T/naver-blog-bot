# Design Spec: Harness Safe Merge

## Goal
Perform a surgical safe merge for `/home/indietogo/projects/naver-blog-bot` that preserves project history and AI-ready context while normalizing only the executable modes required for the harness.

## Invariants
- Preserve `.claude/state.json` cycle history, including the pre-implementation values of `cycle.count` and `cycle.last_cycle_id`.
- Preserve `docs/ai-context`, `CONTEXT.md`, and `CLAUDE.md` without scaffold regeneration or overwrite.
- Preserve existing Python and `uv` configuration.
- Preserve existing lock verification behavior and strength.
- Do not create commits, push branches, tag releases, or run release actions as part of implementation.
- Do not overwrite or discard pre-existing working-tree changes.

## Scope
- Work only in `/home/indietogo/projects/naver-blog-bot`.
- Normalize executable permissions for harness scripts only:
  - `scripts/check.sh` should be tracked with mode `100755`.
  - `.claude/hooks/pre-commit-deny.sh` should be tracked with mode `100755` only if it already exists as a tracked file.
- Keep workflow YAML non-executable:
  - `.github/workflows/ci.yml` should remain tracked with mode `100644`.

## Out of Scope
- Regenerating, reinitializing, or refreshing scaffold files.
- Resetting `.claude/state.json` or cycle history.
- Overwriting `docs/ai-context`, `CONTEXT.md`, or `CLAUDE.md`.
- Changing line-ending policy.
- Overhauling CI behavior.
- Weakening lock verification.
- Creating new harness hook files that do not already exist as tracked files.
- Editing script contents to fix unrelated parse or behavior problems.
- Creating commits, pushing branches, tagging releases, or running release actions.

## Planned Changes
- Inspect the initial working tree before changing anything and note any pre-existing modifications.
- Apply a mode-only normalization to `scripts/check.sh` so it is executable.
- Apply a mode-only normalization to `.claude/hooks/pre-commit-deny.sh` only if that file already exists as a tracked file.
- Ensure `.github/workflows/ci.yml` remains non-executable YAML.
- Avoid content edits. If verification reveals that an existing script cannot parse, stop and report the failure instead of expanding this merge into a script-fix task.

## Verification
- Inspect the changed-file footprint with:
  - `git status --short`
  - `git diff --stat`
  - `git diff --summary`
- Confirm tracked file modes from the repository root with `git ls-files -s --` for these repository-relative paths:
  - `scripts/check.sh`
  - `.claude/hooks/pre-commit-deny.sh`, if tracked
  - `.github/workflows/ci.yml`
- Before and after implementation, parse `.claude/state.json` as JSON and confirm:
  - `cycle.count` remains equal to the pre-implementation value.
  - `cycle.last_cycle_id` remains equal to the pre-implementation value.
- Confirm expected scaffold/context paths still exist and were not overwritten:
  - `docs/ai-context`
  - `CONTEXT.md`
  - `CLAUDE.md`
- Scan for obvious scaffold/template reset markers in preserved context files, using explicit terms such as:
  - `TODO`
  - `TBD`
  - `PLACEHOLDER`
  - `your-project`
  - `example.com`
  - `lorem ipsum`
- Run `bash -n` on each shell script whose mode was changed:
  - `scripts/check.sh`
  - `.claude/hooks/pre-commit-deny.sh`, if touched
- Run the local check script with `./scripts/check.sh` only if required tools are available in the current environment. If skipped, report the exact missing prerequisite or environment limitation.
- Verification is complete only after reporting evidence for file modes, state preservation, scaffold/context preservation, placeholder scan result, shell syntax result, and local check result or explicit skip reason.

## Risks
- A mode-only merge can appear small while accidentally carrying unrelated content changes; diff stat and summary must be reviewed carefully.
- Pre-existing working-tree modifications can be mistaken for implementation changes unless recorded before work begins.
- Regenerating scaffold files would destroy local project context and cycle history.
- Creating a missing hook file would expand scope beyond permission normalization.
- Making CI YAML executable is unnecessary and may obscure the intended minimal permission changes.
- Weakening lock or check behavior could create a false-positive safe merge.

## Implementation Handoff
- Work only in `/home/indietogo/projects/naver-blog-bot`.
- Treat the approved design as a permission-normalization merge, not a scaffold refresh.
- Use mode changes as the only intended implementation mechanism.
- Do not commit, push, tag, or run release actions unless the user explicitly asks in a later instruction.
- Do not overwrite or discard pre-existing user or working-tree changes.
- If a required file is missing, untracked, unparsable, or requires content edits, stop and report the blocker rather than broadening the implementation.
- Before handoff completion, provide verification evidence for file modes, state preservation, scaffold/context preservation, placeholder scan, shell syntax, and local check result where possible.
