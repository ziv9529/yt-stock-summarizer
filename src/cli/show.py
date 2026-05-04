import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.rule import Rule
from rich.text import Text

from src import config
from src.db import get_connection, get_summary, get_video

console = Console()

_STANCE_COLOR = {
    "bullish": "green",
    "bearish": "red",
    "neutral": "yellow",
    "mentioned_only": "dim",
}

_SENTIMENT_COLOR = {
    "bullish": "green",
    "bearish": "red",
    "neutral": "yellow",
}


def _fmt_stance(stance: str) -> Text:
    color = _STANCE_COLOR.get(stance, "white")
    return Text(stance, style=color)


def _show(video_id: str, db_path: Path) -> None:
    with get_connection(db_path) as conn:
        video = get_video(conn, video_id)
        summary = get_summary(conn, video_id)

    if not video:
        console.print(f"[red]Video not found:[/red] {video_id}")
        sys.exit(1)
    if not summary:
        console.print(f"[yellow]No summary yet for:[/yellow] {video['title']}")
        sys.exit(1)

    date_str = video.get("video_date") or "unknown date"
    sentiment = summary.get("overall_sentiment", "neutral")
    score = summary.get("sentiment_score", "?")
    color = _SENTIMENT_COLOR.get(sentiment, "white")

    console.print(Rule(style="dim"))
    title_line = Text()
    title_line.append(f" {video['title']}", style="bold")
    title_line.append(f"  —  {date_str}", style="dim")
    console.print(title_line)

    sentiment_line = Text(" Sentiment: ")
    sentiment_line.append(sentiment.upper(), style=f"bold {color}")
    sentiment_line.append(f"  ({score}/10)", style="dim")
    console.print(sentiment_line)
    console.print(Rule(style="dim"))

    if summary.get("tldr"):
        console.print()
        console.print(" [bold]TL;DR[/bold]")
        console.print(f"  {summary['tldr']}")

    tickers = json.loads(summary.get("tickers_mentioned") or "[]")
    if tickers:
        console.print()
        console.print(" [bold]TICKERS[/bold]")
        for t in tickers:
            symbol = t.get("symbol", "?")
            stance = t.get("stance", "?")
            target = t.get("price_target") or "—"
            rationale = t.get("rationale", "")
            line = Text(f"  {symbol:<8}")
            line.append(f"{stance:<16}", style=_STANCE_COLOR.get(stance, "white"))
            line.append(f"target {target:<10}", style="dim")
            if rationale:
                line.append(f'"{rationale}"', style="italic dim")
            console.print(line)

    key_points = json.loads(summary.get("key_points") or "[]")
    if key_points:
        console.print()
        console.print(" [bold]KEY POINTS[/bold]")
        for kp in key_points:
            ts = kp.get("timestamp", "?")
            point = kp.get("point", "")
            console.print(f"  [dim][{ts}][/dim] {point}")

    quotes = json.loads(summary.get("notable_quotes") or "[]")
    if quotes:
        console.print()
        console.print(" [bold]NOTABLE QUOTES[/bold]")
        for q in quotes:
            ts = q.get("timestamp", "?")
            quote = q.get("quote", "")
            console.print(f'  [dim][{ts}][/dim] [italic]"{quote}"[/italic]')

    if summary.get("macro_views"):
        console.print()
        console.print(" [bold]MACRO VIEWS[/bold]")
        console.print(f"  {summary['macro_views']}")

    topics = json.loads(summary.get("topics") or "[]")
    if topics:
        console.print()
        tags = "  " + "  ".join(f"[dim]{t}[/dim]" for t in topics)
        console.print(tags)

    console.print(Rule(style="dim"))
    console.print(f"  [dim]https://youtube.com/watch?v={video_id}[/dim]")
    console.print()


def _latest_video_id(db_path: Path) -> str | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT v.id FROM videos v
            JOIN summaries s ON s.video_id = v.id
            ORDER BY v.video_date DESC, s.processed_at DESC
            LIMIT 1
            """
        ).fetchone()
    return row["id"] if row else None


@click.command()
@click.argument("video_id", required=False, default=None)
@click.option(
    "--db",
    "db_path",
    default=str(config.DB_PATH),
    show_default=True,
    help="Path to SQLite database file",
)
def show(video_id: str | None, db_path: str) -> None:
    """Pretty-print a video summary. Omit VIDEO_ID to show the most recent."""
    db = Path(db_path)
    if not db.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        sys.exit(1)

    if video_id is None:
        video_id = _latest_video_id(db)
        if video_id is None:
            console.print("[yellow]No processed videos in database yet.[/yellow]")
            sys.exit(0)

    _show(video_id, db)


if __name__ == "__main__":
    show()
