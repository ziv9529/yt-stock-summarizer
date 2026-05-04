import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
TRANSCRIPT_TEXT = """[00:00] Hey everyone welcome back to Fired Up Wealth
[00:02] Today we are going to talk about my top stock picks for the quarter
[00:06] First let's talk about NVIDIA
[00:08] I am very bullish on NVDA going into earnings season
[00:12] The AI infrastructure buildout is still in early innings
[00:15] I think NVDA could hit 150 dollars in the next 12 months
[01:29] Next up is Microsoft MSFT
[01:31] I have a neutral stance here, the valuation is stretched
[02:35] On the macro side, Fed policy is the big wildcard
[02:38] If rates stay higher for longer that puts pressure on growth stocks
[04:30] Overall I am moderately bullish on the market for the rest of the year
[04:34] Thanks for watching"""


def _make_mock_response(summary: dict) -> MagicMock:
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "record_video_analysis"
    tool_block.input = summary

    usage = MagicMock()
    usage.input_tokens = 1000
    usage.output_tokens = 200
    usage.cache_read_input_tokens = 900

    response = MagicMock()
    response.content = [tool_block]
    response.usage = usage
    return response


def test_summarize_video_returns_dict() -> None:
    expected = {
        "is_finance_content": True,
        "tldr": "Bullish on NVDA, neutral on MSFT.",
        "key_points": [{"timestamp": "00:06", "point": "NVDA discussed as top pick."}],
        "tickers_mentioned": [
            {"symbol": "NVDA", "stance": "bullish", "rationale": "AI buildout thesis.", "price_target": "150", "time_horizon": "long_term", "timestamp": "00:06"},
            {"symbol": "MSFT", "stance": "neutral", "rationale": "Valuation stretched.", "price_target": None, "time_horizon": None, "timestamp": "01:29"},
        ],
        "topics": ["AI infrastructure", "semiconductors"],
        "macro_views": "Fed policy is key risk.",
        "overall_sentiment": "bullish",
        "sentiment_score": 7,
        "notable_quotes": [],
    }
    with patch("src.llm.config.ANTHROPIC_API_KEY", "test-key"), \
         patch("src.llm.anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_response(expected)

        from src.llm import LLMClient
        client = LLMClient()
        result = client.summarize_video(TRANSCRIPT_TEXT, "My Top Stock Picks", "2024-03-15")

    assert result["is_finance_content"] is True
    assert result["overall_sentiment"] == "bullish"
    assert result["sentiment_score"] == 7
    assert len(result["tickers_mentioned"]) == 2
    assert result["tickers_mentioned"][0]["symbol"] == "NVDA"


def test_summarize_video_retries_on_rate_limit() -> None:
    import anthropic as anthropic_lib
    expected = {"is_finance_content": False, "tldr": "Not finance.", "key_points": [],
                "tickers_mentioned": [], "topics": [], "macro_views": None,
                "overall_sentiment": "neutral", "sentiment_score": 5, "notable_quotes": []}

    with patch("src.llm.config.ANTHROPIC_API_KEY", "test-key"), \
         patch("src.llm.anthropic.Anthropic") as mock_anthropic_cls, \
         patch("src.llm.time.sleep"):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = [
            anthropic_lib.RateLimitError("rate limited", response=MagicMock(status_code=429), body={}),
            _make_mock_response(expected),
        ]
        from src.llm import LLMClient
        client = LLMClient(max_retries=3, retry_delay=0.0)
        result = client.summarize_video(TRANSCRIPT_TEXT, "Test", None)

    assert result["is_finance_content"] is False


@pytest.mark.integration
def test_real_summarize_video() -> None:
    """Hits the real Anthropic API. Run with: pytest -m integration"""
    from src.llm import LLMClient
    client = LLMClient()
    result = client.summarize_video(TRANSCRIPT_TEXT, "My Top Stock Picks for Q2 2024", "2024-03-15")
    assert "is_finance_content" in result
    assert "tickers_mentioned" in result
    assert isinstance(result["sentiment_score"], int)
