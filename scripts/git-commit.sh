#!/usr/bin/env bash
# Guarded cycle commit.
#
# The WSL<->Windows boundary can terminate a short-lived index-writing git
# invocation in the narrow window AFTER it creates an empty `.git/index.lock`
# (O_CREAT|O_EXCL) but BEFORE it writes the index and renames. git has no TTL
# or stale-lock auto-recovery, so the orphaned 0-byte lock then blocks every
# future index write until removed by hand. This helper clears such an orphan
# — only when one exists AND no git process is alive — then stages + commits.
#
# See docs/ai-context/non-obvious.md (2026-06-07 index.lock entry) and
# docs/ai-context/runbook.md (Commit — WSL stale index.lock guard).
#
# Usage: bash scripts/git-commit.sh -m "feat: ..."
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Pre-write stale-lock guard: act only on a present lock with no live git.
if [ -e .git/index.lock ] && ! pgrep -x git >/dev/null 2>&1; then
  echo "==> clearing stale .git/index.lock (no live git process)"
  rm -f .git/index.lock
fi

git add -A
git commit "$@"
