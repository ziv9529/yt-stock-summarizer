import structlog
from dataclasses import dataclass
from typing import Any

import yt_dlp
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

log = structlog.get_logger()


@dataclass
class VideoMetadata:
    video_id: str
    title: str
    description: str | None
    video_date: str | None  # YYYY-MM-DD
    duration_seconds: int | None
    url: str


def list_channel_videos(channel: str) -> list[VideoMetadata]:
    """Return metadata for every video on a channel handle, e.g. '@FiredUpWealth'."""
    url = f"https://www.youtube.com/{channel}/videos"
    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "extract_flat": True,
        "ignoreerrors": True,
    }
    videos: list[VideoMetadata] = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info or "entries" not in info:
            log.warning("yt_dlp_no_entries", channel=channel)
            return videos
        for entry in info["entries"]:
            if not entry or entry.get("_type") == "playlist":
                continue
            video_id = entry.get("id")
            if not video_id:
                continue
            upload_date = entry.get("upload_date")  # YYYYMMDD string
            video_date = (
                f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
                if upload_date and len(upload_date) == 8
                else None
            )
            videos.append(
                VideoMetadata(
                    video_id=video_id,
                    title=entry.get("title") or video_id,
                    description=entry.get("description"),
                    video_date=video_date,
                    duration_seconds=entry.get("duration"),
                    url=entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
                )
            )
    log.info("channel_videos_listed", channel=channel, count=len(videos))
    return videos


@dataclass
class TranscriptResult:
    segments: list[dict[str, Any]]  # [{text, start, duration}, ...]
    language: str


def fetch_transcript(video_id: str) -> TranscriptResult | None:
    """Fetch transcript segments for a video. Returns None if unavailable."""
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        # Prefer manually created English; fall back to auto-generated
        try:
            transcript = transcript_list.find_manually_created_transcript(["en", "en-US"])
        except NoTranscriptFound:
            transcript = transcript_list.find_generated_transcript(["en", "en-US"])
        fetched = transcript.fetch()
        serialized = [
            {"text": s.text, "start": s.start, "duration": s.duration}
            for s in fetched
        ]
        log.info("transcript_fetched", video_id=video_id, language=fetched.language_code, segments=len(serialized))
        return TranscriptResult(segments=serialized, language=fetched.language_code)
    except TranscriptsDisabled:
        log.warning("transcripts_disabled", video_id=video_id)
        return None
    except NoTranscriptFound:
        log.warning("no_transcript_found", video_id=video_id)
        return None
    except Exception as exc:
        log.error("transcript_fetch_error", video_id=video_id, error=str(exc))
        return None


def segments_to_text(segments: list[dict[str, Any]]) -> str:
    """Flatten transcript segments to plain text with timestamps."""
    lines: list[str] = []
    for seg in segments:
        start = int(seg["start"])
        mm, ss = divmod(start, 60)
        lines.append(f"[{mm:02d}:{ss:02d}] {seg['text'].strip()}")
    return "\n".join(lines)
