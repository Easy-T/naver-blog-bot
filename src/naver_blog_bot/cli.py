import webbrowser
from pathlib import Path
from typing import Annotated

import typer

try:
    import pyperclip as _pyperclip
    _PYPERCLIP_AVAILABLE = True
except ImportError:
    _pyperclip = None  # type: ignore[assignment]
    _PYPERCLIP_AVAILABLE = False

from naver_blog_bot.blog_scraper.service import scrape as scrape_source
from naver_blog_bot.config import Settings, ensure_local_directories, get_settings
from naver_blog_bot.meme_library.service import (
    add_or_update_meme,
    load_meme_index,
    save_meme_index,
    tag_meme_image,
)
from naver_blog_bot.post_generator.drafts import DraftRepository
from naver_blog_bot.post_generator.generator import PostGenerator
from naver_blog_bot.shared.claude_client import ClaudeBackendError, build_text_completer
from naver_blog_bot.style_profiler.examples import ExamplePost, FewShotRepository
from naver_blog_bot.style_profiler.refresh import refresh_style_profile
from naver_blog_bot.style_profiler.service import (
    load_style_profile,
    save_style_profile,
    style_profile_path,
    validate_profile_name,
)

app = typer.Typer(no_args_is_help=True)


def build_generator(settings: Settings) -> PostGenerator:
    return PostGenerator(
        settings=settings, claude_client=build_text_completer(settings)
    )


def _is_url_source(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


@app.command("init")
def init_command() -> None:
    settings = get_settings()
    created = ensure_local_directories(settings)
    typer.echo("Local project state is ready:")
    for path in created:
        typer.echo(f"- {path}")
    typer.echo("Naver browser login automation is outside this foundation slice.")


@app.command("profile-refresh")
def profile_refresh_command(
    sources: Annotated[
        list[str],
        typer.Argument(
            help="One or more local sample post files and/or HTTP/HTTPS URLs."
        ),
    ],
    profile: Annotated[
        str,
        typer.Option("--profile", help="Style profile name. Default: 'default'."),
    ] = "default",
    count: Annotated[
        int,
        typer.Option("--count", help="Number of posts to scrape per URL source."),
    ] = 5,
) -> None:
    settings = get_settings()
    ensure_local_directories(settings)

    try:
        validate_profile_name(profile)
    except ValueError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)

    if not sources:
        typer.echo("Error: provide at least one sample post file or URL")
        raise typer.Exit(1)

    if count < 1:
        typer.echo("Error: count must be at least 1")
        raise typer.Exit(1)

    sample_texts: list[str] = []
    url_examples: list[ExamplePost] = []
    first_url: str | None = None

    for source in sources:
        if _is_url_source(source):
            if first_url is None:
                first_url = source
            try:
                docs = scrape_source(source, count, settings)
            except ValueError as exc:
                typer.echo(f"Error: {exc}")
                raise typer.Exit(1)
            if not docs:
                typer.echo(f"Error: no posts found at {source}")
                raise typer.Exit(1)
            for doc in docs:
                sample_texts.append(doc.to_structured_text())
                url_examples.append(
                    ExamplePost(
                        title=doc.title or "",
                        url=doc.url,
                        structured_text=doc.to_structured_text(),
                    )
                )
        else:
            path = Path(source)
            if not path.is_file():
                typer.echo(f"Error: sample file not found: {source}")
                raise typer.Exit(1)
            sample_texts.append(path.read_text(encoding="utf-8"))

    blog_url = first_url if first_url is not None else settings.blog_url

    try:
        result = refresh_style_profile(
            profile_name=profile,
            blog_url=blog_url,
            sample_texts=sample_texts,
            completer=build_text_completer(settings),
        )
    except ClaudeBackendError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)
    except ValueError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)

    save_path = style_profile_path(settings, profile)
    save_style_profile(save_path, result)

    if url_examples:
        examples_path = settings.style_profiles_dir / f"{profile}-examples.json"
        FewShotRepository(examples_path).save(url_examples)

    typer.echo(f"Style profile saved: {save_path} ({len(sample_texts)} sample(s) used)")


@app.command("draft")
def draft_command(
    items: Annotated[
        list[str],
        typer.Argument(
            help="One or more photo paths followed by the memo as the final argument."
        ),
    ],
    profile: Annotated[
        str,
        typer.Option("--profile", help="Style profile name. Default: 'default'."),
    ] = "default",
) -> None:
    if len(items) < 2:
        typer.echo("Error: provide at least one photo path and a memo")
        raise typer.Exit(1)

    settings = get_settings()
    ensure_local_directories(settings)
    photo_paths = [Path(item) for item in items[:-1]]
    memo = items[-1]
    missing = [path for path in photo_paths if not path.exists()]
    if missing:
        typer.echo(f"Error: photo not found: {missing[0]}")
        raise typer.Exit(1)

    try:
        validate_profile_name(profile)
    except ValueError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)

    named_path = style_profile_path(settings, profile)
    if not named_path.exists():
        typer.echo(
            f"Style profile not found: {profile}. "
            f"Run profile-refresh --profile {profile} first."
        )
        raise typer.Exit(1)

    style_profile = load_style_profile(named_path, settings.blog_url)
    examples_path = settings.style_profiles_dir / f"{profile}-examples.json"
    examples = FewShotRepository(examples_path).load() or None
    meme_index = load_meme_index(settings.meme_index_path)
    try:
        draft = build_generator(settings).generate(
            photo_paths=photo_paths,
            memo=memo,
            style_profile=style_profile,
            meme_index=meme_index,
            examples=examples,
        )
    except ClaudeBackendError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)
    DraftRepository(settings.drafts_dir).save(draft)
    typer.echo(f"Draft saved: {draft.id}")


@app.command("preview")
def preview_command(
    draft_id: Annotated[str, typer.Argument(help="Draft ID to preview.")],
) -> None:
    settings = get_settings()
    try:
        draft = DraftRepository(settings.drafts_dir).load(draft_id)
    except FileNotFoundError:
        typer.echo(f"Draft not found: {draft_id}")
        raise typer.Exit(1)

    html_path = settings.drafts_dir / f"{draft_id}.html"
    html_path.write_text(draft.to_html(), encoding="utf-8")
    webbrowser.open(html_path.as_uri())

    if _PYPERCLIP_AVAILABLE:
        try:
            _pyperclip.copy(draft.body_markdown)
            typer.echo(f"Preview opened: {html_path}\nContent copied to clipboard.")
        except Exception:
            typer.echo(
                f"Preview opened: {html_path}\n"
                "(Clipboard copy failed — install xclip or xsel on WSL2.)"
            )
    else:
        typer.echo(
            f"Preview opened: {html_path}\n"
            "(pyperclip not available — run 'uv sync' to enable clipboard.)"
        )


@app.command("meme-add")
def meme_add_command(
    image_path: Annotated[Path, typer.Argument(help="Path to meme image file.")],
) -> None:
    if not image_path.is_file():
        typer.echo(f"Error: file not found: {image_path}")
        raise typer.Exit(1)
    settings = get_settings()
    try:
        asset = tag_meme_image(image_path, build_text_completer(settings))
    except (ClaudeBackendError, ValueError) as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)
    index = load_meme_index(settings.meme_index_path)
    updated = add_or_update_meme(index, asset)
    save_meme_index(settings.meme_index_path, updated)
    typer.echo(f"Added: {image_path.name} (tags: {', '.join(asset.tags)})")


@app.command("meme-build")
def meme_build_command() -> None:
    settings = get_settings()
    ensure_local_directories(settings)
    index = load_meme_index(settings.meme_index_path)
    existing_ids = {m.id for m in index.memes}
    extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    new_count = 0
    for image_path in sorted(settings.memes_dir.iterdir()):
        if image_path.suffix.lower() not in extensions:
            continue
        if image_path.stem in existing_ids:
            continue
        try:
            asset = tag_meme_image(image_path, build_text_completer(settings))
            index = add_or_update_meme(index, asset)
            new_count += 1
            typer.echo(f"Tagged: {image_path.name}")
        except (ClaudeBackendError, ValueError) as exc:
            typer.echo(f"Skipped {image_path.name}: {exc}")
    save_meme_index(settings.meme_index_path, index)
    skipped = len(existing_ids)
    typer.echo(f"Done: {new_count} new image(s) tagged, {skipped} existing skipped.")


@app.command("publish")
def publish_command(
    draft_id: Annotated[str, typer.Argument(help="Draft ID to publish.")],
) -> None:
    typer.echo("publish is outside this foundation slice.")
    raise typer.Exit(1)


def main() -> None:
    app()
