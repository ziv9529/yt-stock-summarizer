import json
import pytest
from pathlib import Path
from src.db import (
    init_db,
    get_connection,
    upsert_channel,
    upsert_video,
    upsert_summary,
    update_transcript,
    get_video,
    get_summary,
    list_unprocessed,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    return path


def test_init_db_creates_tables(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"channels", "videos", "summaries"}.issubset(tables)


def test_upsert_channel(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        upsert_channel(conn, "@FiredUpWealth", "Fired Up Wealth")
        row = conn.execute("SELECT * FROM channels WHERE id = ?", ("@FiredUpWealth",)).fetchone()
    assert row["name"] == "Fired Up Wealth"


def test_upsert_channel_updates_name(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        upsert_channel(conn, "@FiredUpWealth", "Old Name")
        upsert_channel(conn, "@FiredUpWealth", "New Name")
        row = conn.execute("SELECT name FROM channels WHERE id = ?", ("@FiredUpWealth",)).fetchone()
    assert row["name"] == "New Name"


def test_upsert_video(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        upsert_channel(conn, "@FiredUpWealth", "Fired Up Wealth")
        upsert_video(conn, "abc123", "@FiredUpWealth", "My Stock Pick", "Description", "2024-03-15", 720)
        video = get_video(conn, "abc123")
    assert video is not None
    assert video["title"] == "My Stock Pick"
    assert video["video_date"] == "2024-03-15"
    assert video["duration_seconds"] == 720


def test_upsert_video_idempotent(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        upsert_channel(conn, "@FiredUpWealth", "Fired Up Wealth")
        upsert_video(conn, "abc123", "@FiredUpWealth", "Title v1", None, None, None)
        upsert_video(conn, "abc123", "@FiredUpWealth", "Title v2", None, "2024-04-01", None)
        video = get_video(conn, "abc123")
    assert video["title"] == "Title v2"
    assert video["video_date"] == "2024-04-01"


def test_update_transcript(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        upsert_channel(conn, "@FiredUpWealth", "Fired Up Wealth")
        upsert_video(conn, "abc123", "@FiredUpWealth", "Title", None, None, None)
        update_transcript(conn, "abc123", "Hello world transcript", "en")
        video = get_video(conn, "abc123")
    assert video["transcript"] == "Hello world transcript"
    assert video["transcript_language"] == "en"


def test_upsert_summary(db_path: Path) -> None:
    summary = {
        "is_finance_content": True,
        "tldr": "Bullish on NVDA.",
        "key_points": [{"timestamp": "01:23", "point": "NVDA earnings beat."}],
        "tickers_mentioned": [{"symbol": "NVDA", "stance": "bullish", "rationale": "Strong earnings."}],
        "topics": ["AI", "semiconductors"],
        "macro_views": None,
        "overall_sentiment": "bullish",
        "sentiment_score": 8,
        "notable_quotes": [],
    }
    with get_connection(db_path) as conn:
        upsert_channel(conn, "@FiredUpWealth", "Fired Up Wealth")
        upsert_video(conn, "abc123", "@FiredUpWealth", "NVDA Review", None, "2024-03-01", None)
        upsert_summary(conn, "abc123", summary)
        row = get_summary(conn, "abc123")
    assert row is not None
    assert row["tldr"] == "Bullish on NVDA."
    assert row["overall_sentiment"] == "bullish"
    assert row["sentiment_score"] == 8
    assert json.loads(row["tickers_mentioned"])[0]["symbol"] == "NVDA"


def test_get_video_missing(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        assert get_video(conn, "nonexistent") is None


def test_list_unprocessed(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        upsert_channel(conn, "@FiredUpWealth", "Fired Up Wealth")
        upsert_video(conn, "v1", "@FiredUpWealth", "Video 1", None, "2024-01-01", None)
        upsert_video(conn, "v2", "@FiredUpWealth", "Video 2", None, "2024-01-02", None)
        upsert_summary(conn, "v1", {
            "is_finance_content": True, "tldr": "t", "key_points": [],
            "tickers_mentioned": [], "topics": [], "macro_views": None,
            "overall_sentiment": "neutral", "sentiment_score": 5, "notable_quotes": [],
        })
        unprocessed = list_unprocessed(conn, "@FiredUpWealth")
    assert len(unprocessed) == 1
    assert unprocessed[0]["id"] == "v2"
