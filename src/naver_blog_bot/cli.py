from pathlib import Path
from typing import Annotated

import typer

from naver_blog_bot.config import Settings, ensure_local_directories, get_settings
from naver_blog_bot.meme_library.service import load_meme_index
from naver_blog_bot.post_generator.drafts import DraftRepository
from naver_blog_bot.post_generator.generator import PostGenerator
from naver_blog_bot.shared.claude_client import ClaudeTextClient
from naver_blog_bot.style_profiler.service import load_style_profile

app = typer.Typer(no_args_is_help=True)


def build_generator(settings: Settings) -> PostGenerator:
    return PostGenerator(settings=settings, claude_client=ClaudeTextClient(settings=settings))


@app.command("init")
def init_command() -> None:
    settings = get_settings()
    created = ensure_local_directories(settings)
    typer.echo("Local project state is ready:")
    for path in created:
        typer.echo(f"- {path}")
    typer.echo("Naver browser login automation is outside this foundation slice.")


@app.command("draft")
def draft_command(
    items: Annotated[
        list[str],
        typer.Argument(help="One or more photo paths followed by the memo as the final argument."),
    ],
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

    style_profile = load_style_profile(settings.style_profile_path, settings.blog_url)
    meme_index = load_meme_index(settings.meme_index_path)
    draft = build_generator(settings).generate(
        photo_paths=photo_paths,
        memo=memo,
        style_profile=style_profile,
        meme_index=meme_index,
    )
    DraftRepository(settings.drafts_dir).save(draft)
    typer.echo(f"Draft saved: {draft.id}")


@app.command("preview")
def preview_command(draft_id: Annotated[str, typer.Argument(help="Draft ID to preview.")]) -> None:
    settings = get_settings()
    try:
        draft = DraftRepository(settings.drafts_dir).load(draft_id)
    except FileNotFoundError:
        typer.echo(f"Draft not found: {draft_id}")
        raise typer.Exit(1)
    typer.echo(draft.preview_text())


@app.command("profile-refresh")
def profile_refresh_command() -> None:
    typer.echo("profile-refresh is outside this foundation slice.")
    raise typer.Exit(1)


@app.command("meme-build")
def meme_build_command() -> None:
    typer.echo("meme-build is outside this foundation slice.")
    raise typer.Exit(1)


@app.command("publish")
def publish_command(draft_id: Annotated[str, typer.Argument(help="Draft ID to publish.")]) -> None:
    typer.echo("publish is outside this foundation slice.")
    raise typer.Exit(1)


def main() -> None:
    app()
