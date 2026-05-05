import sys
from pathlib import Path

import click
import structlog
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src import config
from src.db import get_connection, init_db, upsert_channel, upsert_video
from src.process_video import process_video_metadata
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


def list_unfetched_transcripts(conn, channel_id: str) -> list[dict]:
    # Custom query because list_unprocessed checks the summaries table
    rows = conn.execute(
        """
        SELECT id, title, video_date
        FROM videos
        WHERE channel_id = ? AND transcript IS NULL
        ORDER BY video_date DESC
        """,
        (channel_id,)
    ).fetchall()
    return [dict(r) for r in rows]


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
def ingest(channel: str, limit: int, db_path: str, log_level: str) -> None:
    """Ingest all video metadata and transcripts from a YouTube channel into the local database (0 AI calls)."""
    _configure_logging(log_level)
    db = Path(db_path)
    init_db(db)

    from rich.console import Console
    console = Console()

    with console.status(f"[bold green]Listing all videos for {channel} (this takes a moment)..."):
        videos = list_channel_videos(channel)
        
    if not videos:
        click.echo("No videos found.", err=True)
        raise SystemExit(1)
    
    console.print(f"[bold blue]Found {len(videos)} videos on channel.[/bold blue]")

    with console.status("[bold green]Saving video metadata to database..."):
        with get_connection(db) as conn:
            upsert_channel(conn, channel, channel)
            for v in videos:
                upsert_video(conn, v.video_id, channel, v.title, v.description, v.video_date, v.duration_seconds)

    with get_connection(db) as conn:
        todo = list_unfetched_transcripts(conn, channel)

    if not todo:
        click.echo("All videos already ingested (have transcripts or tried and failed).")
        return

    if limit > 0:
        todo = todo[:limit]

    click.echo(f"{len(todo)} video(s) to fetch transcripts for.")
    processed = skipped = errors = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        transient=False,
    ) as progress:
        task = progress.add_task("Fetching transcripts", total=len(todo))

        for video in todo:
            video_id = video["id"]
            title = video["title"]
            progress.update(task, description=f"[cyan]{title[:60]}")
            try:
                did_process = process_video_metadata(
                    video_id=video_id,
                    title=title,
                    db_path=db,
                )
                if did_process:
                    processed += 1
                else:
                    skipped += 1
            except Exception as exc:
                log.error("process_video_metadata_failed", video_id=video_id, error=str(exc))
                errors += 1
            finally:
                progress.advance(task)

    click.echo(f"\nDone. Fetched: {processed}  Skipped: {skipped}  Errors: {errors}")


if __name__ == "__main__":
    ingest()
