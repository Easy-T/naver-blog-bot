#!/usr/bin/env bash
# scripts/check.sh — local quality gate for naver-blog-bot
# Run before every PR. Must pass before gh pr create.
set -euo pipefail

echo "== naver-blog-bot check =="

uv run ruff check . && uv run ruff format --check . && uv run pytest -q

echo "== check complete =="
