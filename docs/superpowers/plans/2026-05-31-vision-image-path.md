**Status:** completed
**RPI-Cycle:** 9
**Started:** 2026-05-31

# Claude Code Vision via Prompt Image Path — Implementation Plan

**Goal:** `ClaudeCodeTextClient.complete_vision`이 존재하지 않는 `--image` 옵션 대신, 프롬프트에 이미지 절대경로를 임베드해 Claude Code가 Read 도구로 분석하도록 고친다.

**Architecture:** `shared/claude_client.py`의 `ClaudeCodeTextClient.complete_vision` 한 메서드만 변경. SDK 백엔드·meme 로직 불변.

**Tech Stack:** Python 3.11+, Claude Code CLI subprocess, pytest, ruff.

---

## Task 1: complete_vision 프롬프트 경로 방식으로 수정

**Files:**
- Modify: `src/naver_blog_bot/shared/claude_client.py`
- Test: `tests/unit/test_claude_client.py`

- [x] **Step 1: 기존 테스트를 새 동작으로 교체**

`tests/unit/test_claude_client.py`의 `test_claude_code_vision_client_builds_correct_args`를 아래로 교체:

```python
def test_claude_code_vision_client_builds_correct_args(monkeypatch) -> None:
    calls = []

    def fake_run(args, *, input, capture_output, text, check, timeout):
        calls.append({"args": args, "input": input})
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps({"type": "result", "result": "OK"}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = ClaudeCodeTextClient(settings=Settings())
    result = client.complete_vision(
        image_path=Path("/tmp/test.jpg"), prompt="이 이미지를 분석"
    )

    assert result == "OK"
    # --image option does not exist in the installed CLI; must NOT be used.
    assert "--image" not in calls[0]["args"]
    # The absolute image path is embedded in the prompt sent on stdin.
    assert "/tmp/test.jpg" in calls[0]["input"]
    assert "이 이미지를 분석" in calls[0]["input"]
```

- [x] **Step 2: 실패 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_claude_client.py -k "vision_client_builds_correct_args" -q 2>&1 | tail -10
```
Expected: FAIL (현재 코드는 `--image` 사용).

- [x] **Step 3: complete_vision 수정**

`src/naver_blog_bot/shared/claude_client.py`의 `ClaudeCodeTextClient.complete_vision`에서 args의 `--image`/경로를 제거하고 프롬프트에 절대경로를 임베드한다. 현재:

```python
    def complete_vision(self, *, image_path: Path, prompt: str) -> str:
        args = [
            self.settings.claude_command,
            "-p",
            "--output-format",
            "json",
            "--model",
            self.settings.claude_model,
            "--image",
            str(image_path),
        ]
        try:
            result = subprocess.run(
                args,
                input=prompt,
```

를 아래로 교체:

```python
    def complete_vision(self, *, image_path: Path, prompt: str) -> str:
        abs_path = Path(image_path).resolve()
        full_prompt = f"{prompt}\n\n분석할 이미지 파일 경로: {abs_path}"
        args = [
            self.settings.claude_command,
            "-p",
            "--output-format",
            "json",
            "--model",
            self.settings.claude_model,
        ]
        try:
            result = subprocess.run(
                args,
                input=full_prompt,
```

(이후 `capture_output=True, text=True, check=False, timeout=...` 및 에러 처리·`_parse_output`은 그대로 유지.)

- [x] **Step 4: 통과 확인**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/unit/test_claude_client.py -q 2>&1 | tail -6
```
Expected: PASS.

- [x] **Step 5: 전체 테스트 + ruff**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run pytest tests/ -q 2>&1 | tail -3 && uv run ruff check src/ tests/
```
Expected: ALL PASS + clean.

- [x] **Step 6: 커밋**

```bash
cd /home/indietogo/projects/naver-blog-bot && git add src/naver_blog_bot/shared/claude_client.py tests/unit/test_claude_client.py && git commit -m "fix: pass image path in prompt for Claude Code vision (no --image option)"
```

---

## Task 2: 실제 meme-add 스모크

- [x] **Step 1: 품질 게이트**

```bash
cd /home/indietogo/projects/naver-blog-bot && bash scripts/check.sh
```
Expected: exit 0.

- [x] **Step 2: 실제 meme-add (Claude Vision 호출)**

```bash
cd /home/indietogo/projects/naver-blog-bot && uv run naver-bot meme-add sim/meme_smile.png
```
Expected: `Added: meme_smile.png (tags: ...)`. `config/meme_index.json`에 등록.

---

## Self-Review

- Spec 커버리지: complete_vision 수정(Task 1) + 실제 검증(Task 2).
- Placeholder 없음. 범위: claude_client.py + 테스트만.
- 타입 일관성: complete_vision 시그니처 불변(image_path, prompt). 내부 구현만 변경.
