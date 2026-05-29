from pathlib import Path

from naver_blog_bot.style_profiler.examples import ExamplePost, FewShotRepository


def test_few_shot_repository_round_trip(tmp_path: Path) -> None:
    repo = FewShotRepository(tmp_path / "examples.json")
    examples = [
        ExamplePost(
            title="카페 후기",
            url="https://blog.naver.com/flowerbend/1",
            structured_text="오늘 방문한 카페는 [이미지] 분위기가 정말 좋았어요.",
        ),
        ExamplePost(
            title="제품 리뷰",
            url="https://blog.naver.com/flowerbend/2",
            structured_text="이 제품 너무 마음에 들어요. [이모티콘:만족]",
        ),
    ]
    repo.save(examples)
    loaded = repo.load()
    assert len(loaded) == 2
    assert loaded[0].title == "카페 후기"
    assert loaded[1].structured_text == "이 제품 너무 마음에 들어요. [이모티콘:만족]"


def test_few_shot_repository_missing_file_returns_empty(tmp_path: Path) -> None:
    repo = FewShotRepository(tmp_path / "missing.json")
    assert repo.load() == []
    assert not repo.exists()


def test_few_shot_repository_exists_after_save(tmp_path: Path) -> None:
    repo = FewShotRepository(tmp_path / "examples.json")
    repo.save([ExamplePost(title="t", url="u", structured_text="s")])
    assert repo.exists()


def test_few_shot_repository_saves_at_most_three(tmp_path: Path) -> None:
    repo = FewShotRepository(tmp_path / "examples.json")
    examples = [
        ExamplePost(title=f"글{i}", url=f"url{i}", structured_text=f"본문{i}")
        for i in range(5)
    ]
    repo.save(examples)
    assert len(repo.load()) == 3
