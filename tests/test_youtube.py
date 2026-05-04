import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.youtube import VideoMetadata, TranscriptResult, list_channel_videos, fetch_transcript, segments_to_text

FIXTURES = Path(__file__).parent / "fixtures"


def test_segments_to_text() -> None:
    segments = [
        {"text": "Hello world", "start": 0.0, "duration": 2.0},
        {"text": "This is a test", "start": 65.0, "duration": 2.0},
    ]
    result = segments_to_text(segments)
    assert "[00:00] Hello world" in result
    assert "[01:05] This is a test" in result


def test_segments_to_text_with_fixture() -> None:
    segments = json.loads((FIXTURES / "sample_transcript.json").read_text())
    text = segments_to_text(segments)
    assert "[00:00]" in text
    assert "NVIDIA" in text


def test_fetch_transcript_returns_none_on_disabled() -> None:
    from youtube_transcript_api import TranscriptsDisabled
    with patch("src.youtube.YouTubeTranscriptApi") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.list.side_effect = TranscriptsDisabled("test_id")
        result = fetch_transcript("test_id")
    assert result is None


def test_fetch_transcript_returns_none_on_no_transcript() -> None:
    from youtube_transcript_api import NoTranscriptFound
    with patch("src.youtube.YouTubeTranscriptApi") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.list.side_effect = NoTranscriptFound("test_id", ["en"], {})
        result = fetch_transcript("test_id")
    assert result is None


def test_list_channel_videos_empty_channel() -> None:
    with patch("src.youtube.yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"entries": []}
        result = list_channel_videos("@TestChannel")
    assert result == []


def test_list_channel_videos_parses_entries() -> None:
    fake_entries = [
        {
            "id": "vid001",
            "title": "NVDA Analysis",
            "description": "Deep dive",
            "upload_date": "20240315",
            "duration": 600,
            "url": "https://www.youtube.com/watch?v=vid001",
            "_type": "video",
        }
    ]
    with patch("src.youtube.yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"entries": fake_entries}
        result = list_channel_videos("@TestChannel")
    assert len(result) == 1
    assert result[0].video_id == "vid001"
    assert result[0].video_date == "2024-03-15"
    assert result[0].duration_seconds == 600


@pytest.mark.integration
def test_fetch_real_transcript() -> None:
    """Hits the real YouTube API. Run with: pytest -m integration"""
    result = fetch_transcript("dQw4w9WgXcQ")  # a well-known public video
    assert result is None or isinstance(result, TranscriptResult)
