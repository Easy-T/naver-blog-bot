# naver-blog-bot

> AI-Ready 코드베이스. 이 파일은 모든 세션의 prefix에 자동 로드됩니다.
> 변경은 세션 종료 직전에만 (캐시 미스 비용 ≈20배).
> ≤200줄 유지. 백과사전이 아닌 나침반.

Created: 2026-05-02

## Stack
Python 3.11+ / uv / Typer / Playwright / anthropic SDK / pydantic-settings / JSON file storage

## Modules
- `config.py` — pydantic-settings configuration and local state paths
- `storage/json_store.py` — deterministic UTF-8 JSON persistence helpers
- `style_profiler` — style profile schema and JSON loader/saver
- `meme_library` — meme asset/index schema and JSON loader/saver
- `photo_describer` — 사진을 vision으로 캡션 (EXIF 보정·다운스케일·content-hash 캐시)
- `post_generator` — draft models, repository, and Claude-backed generation service
- `shared/claude_client.py` — centralized Anthropic SDK text request wrapper
- `cli.py` — Typer command surface for init, draft, preview, and blocked future commands

## Top 5 Non-Obvious Patterns
참조: [docs/ai-context/non-obvious.md](docs/ai-context/non-obvious.md)

(아직 누적되지 않음)

## Pointers
- 절대 금지: [docs/ai-context/deny-patterns.md](docs/ai-context/deny-patterns.md)
- 아키텍처: [docs/ai-context/architecture.md](docs/ai-context/architecture.md)
- 운영·배포: [docs/ai-context/runbook.md](docs/ai-context/runbook.md)
- 도메인 용어: [docs/ai-context/domain-glossary.md](docs/ai-context/domain-glossary.md)
