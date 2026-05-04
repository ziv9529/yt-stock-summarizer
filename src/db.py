import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    id   TEXT PRIMARY KEY,
    name TEXT,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS videos (
    id                  TEXT PRIMARY KEY,
    channel_id          TEXT NOT NULL REFERENCES channels(id),
    title               TEXT NOT NULL,
    description         TEXT,
    video_date          TEXT,
    duration_seconds    INTEGER,
    transcript          TEXT,
    transcript_language TEXT,
    fetched_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS summaries (
    video_id         TEXT PRIMARY KEY REFERENCES videos(id),
    is_finance_content INTEGER NOT NULL,
    tldr             TEXT,
    key_points       TEXT,
    tickers_mentioned TEXT,
    topics           TEXT,
    macro_views      TEXT,
    overall_sentiment TEXT,
    sentiment_score  INTEGER,
    notable_quotes   TEXT,
    important_notes  TEXT,
    processed_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@contextmanager
def get_connection(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)


def upsert_channel(conn: sqlite3.Connection, channel_id: str, name: str) -> None:
    conn.execute(
        "INSERT INTO channels (id, name) VALUES (?, ?)"
        " ON CONFLICT(id) DO UPDATE SET name = excluded.name",
        (channel_id, name),
    )


def upsert_video(
    conn: sqlite3.Connection,
    video_id: str,
    channel_id: str,
    title: str,
    description: str | None,
    video_date: str | None,
    duration_seconds: int | None,
) -> None:
    conn.execute(
        """
        INSERT INTO videos (id, channel_id, title, description, video_date, duration_seconds)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title            = excluded.title,
            description      = excluded.description,
            video_date       = excluded.video_date,
            duration_seconds = excluded.duration_seconds
        """,
        (video_id, channel_id, title, description, video_date, duration_seconds),
    )


def update_transcript(
    conn: sqlite3.Connection,
    video_id: str,
    transcript: str,
    language: str,
) -> None:
    conn.execute(
        "UPDATE videos SET transcript = ?, transcript_language = ? WHERE id = ?",
        (transcript, language, video_id),
    )


def upsert_summary(conn: sqlite3.Connection, video_id: str, summary: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO summaries (
            video_id, is_finance_content, tldr, key_points, tickers_mentioned,
            topics, macro_views, overall_sentiment, sentiment_score, notable_quotes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id) DO UPDATE SET
            is_finance_content = excluded.is_finance_content,
            tldr               = excluded.tldr,
            key_points         = excluded.key_points,
            tickers_mentioned  = excluded.tickers_mentioned,
            topics             = excluded.topics,
            macro_views        = excluded.macro_views,
            overall_sentiment  = excluded.overall_sentiment,
            sentiment_score    = excluded.sentiment_score,
            notable_quotes     = excluded.notable_quotes,
            processed_at       = datetime('now')
        """,
        (
            video_id,
            int(summary["is_finance_content"]),
            summary.get("tldr"),
            json.dumps(summary.get("key_points", [])),
            json.dumps(summary.get("tickers_mentioned", [])),
            json.dumps(summary.get("topics", [])),
            summary.get("macro_views"),
            summary.get("overall_sentiment"),
            summary.get("sentiment_score"),
            json.dumps(summary.get("notable_quotes", [])),
        ),
    )


def get_video(conn: sqlite3.Connection, video_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    return dict(row) if row else None


def get_summary(conn: sqlite3.Connection, video_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM summaries WHERE video_id = ?", (video_id,)).fetchone()
    return dict(row) if row else None


def list_unprocessed(conn: sqlite3.Connection, channel_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT v.* FROM videos v
        LEFT JOIN summaries s ON s.video_id = v.id
        WHERE v.channel_id = ? AND s.video_id IS NULL
        ORDER BY v.video_date DESC
        """,
        (channel_id,),
    ).fetchall()
    return [dict(row) for row in rows]
