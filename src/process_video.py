import structlog
from pathlib import Path
from typing import Any

from src import config
from src.db import get_connection, get_summary, update_transcript, upsert_summary
from src.llm import LLMClient
from src.youtube import fetch_transcript, segments_to_text

log = structlog.get_logger()

_FINANCE_KEYWORDS = {
    "stock", "stocks", "invest", "investing", "investment", "portfolio",
    "buy", "sell", "bull", "bear", "earnings", "revenue", "market",
    "ticker", "share", "shares", "dividend", "etf", "fund", "trade",
    "trading", "equity", "valuation", "price target", "analysis",
    "nasdaq", "s&p", "dow", "nyse", "crypto", "bitcoin",
}


def _looks_like_finance(title: str) -> bool:
    lower = title.lower()
    return any(kw in lower for kw in _FINANCE_KEYWORDS)


def process_video(
    video_id: str,
    title: str,
    video_date: str | None,
    db_path: Path,
    client: LLMClient,
    skip_non_finance: bool = False,
) -> bool:
    """Fetch transcript, call Claude, persist summary. Returns True if processed, False if skipped.

    Idempotent: if a summary already exists the video is skipped.
    Atomic: if Claude fails, no partial summary row is written.
    """
    with get_connection(db_path) as conn:
        if get_summary(conn, video_id) is not None:
            log.debug("video_already_processed", video_id=video_id)
            return False

    if skip_non_finance and not _looks_like_finance(title):
        log.info("title_filter_skip", video_id=video_id, title=title)
        return False

    transcript_result = fetch_transcript(video_id)
    if transcript_result is None:
        log.warning("no_transcript_skipping", video_id=video_id)
        return False

    transcript_text = segments_to_text(transcript_result.segments)

    with get_connection(db_path) as conn:
        update_transcript(conn, video_id, transcript_text, transcript_result.language)

    summary: dict[str, Any] = client.summarize_video(transcript_text, title, video_date)

    with get_connection(db_path) as conn:
        upsert_summary(conn, video_id, summary)

    log.info(
        "video_processed",
        video_id=video_id,
        title=title,
        is_finance=summary.get("is_finance_content"),
        sentiment=summary.get("overall_sentiment"),
        score=summary.get("sentiment_score"),
        tickers=[t["symbol"] for t in summary.get("tickers_mentioned", [])],
    )
    return True
