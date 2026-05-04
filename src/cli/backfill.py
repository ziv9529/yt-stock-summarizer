import sys
from pathlib import Path

import click
import structlog
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src import config
from src.db import get_connection, init_db, list_unprocessed, upsert_channel, upsert_video
from src.llm import LLMClient
from src.process_video import process_video
from src.youtube import list_channel_videos

log = structlog.get_logger()


def _configure_logging(level: str) -> None:
    import logging
    import structlog
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), stream=sys.stderr)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
    )


@click.command()
@click.option("--channel", required=True, help="YouTube channel handle, e.g. @FiredUpWealth")
@click.option("--limit", default=0, show_default=True, help="Process at most N videos (0 = all)")
@click.option(
    "--db",
    "db_path",
    default=str(config.DB_PATH),
    show_default=True,
    help="Path to SQLite database file",
)
@click.option("--log-level", default=config.LOG_LEVEL, show_default=True, help="Logging level")
def backfill(channel: str, limit: int, db_path: str, log_level: str) -> None:
    """Backfill all videos from a YouTube channel into the local database."""
    _configure_logging(log_level)
    db = Path(db_path)
    init_db(db)

    click.echo(f"Listing videos for {channel}...")
    videos = list_channel_videos(channel)
    if not videos:
        click.echo("No videos found.", err=True)
        raise SystemExit(1)
    click.echo(f"Found {len(videos)} videos on channel.")

    with get_connection(db) as conn:
        upsert_channel(conn, channel, channel)
        for v in videos:
            upsert_video(conn, v.video_id, channel, v.title, v.description, v.video_date, v.duration_seconds)

    with get_connection(db) as conn:
        todo = list_unprocessed(conn, channel)

    if not todo:
        click.echo("All videos already processed.")
        return

    if limit > 0:
        todo = todo[:limit]

    click.echo(f"{len(todo)} video(s) to process.")
    client = LLMClient()
    processed = skipped = errors = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        transient=False,
    ) as progress:
        task = progress.add_task("Processing videos", total=len(todo))

        for video in todo:
            video_id = video["id"]
            title = video["title"]
            progress.update(task, description=f"[cyan]{title[:60]}")
            try:
                did_process = process_video(
                    video_id=video_id,
                    title=title,
                    video_date=video["video_date"],
                    db_path=db,
                    client=client,
                )
                if did_process:
                    processed += 1
                else:
                    skipped += 1
            except Exception as exc:
                log.error("process_video_failed", video_id=video_id, error=str(exc))
                errors += 1
            finally:
                progress.advance(task)

    click.echo(f"\nDone. Processed: {processed}  Skipped: {skipped}  Errors: {errors}")


if __name__ == "__main__":
    backfill()
