import json
import time
from pathlib import Path
from typing import Any

import anthropic
import structlog

from src import config

log = structlog.get_logger()

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_system_prompt() -> str:
    return (_PROMPTS_DIR / "system.txt").read_text(encoding="utf-8")


def _load_schema() -> dict[str, Any]:
    return json.loads((_PROMPTS_DIR / "schema.json").read_text(encoding="utf-8"))


class LLMClient:
    def __init__(self, max_retries: int = 3, retry_delay: float = 5.0) -> None:
        if not config.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._system_prompt = _load_system_prompt()
        self._schema = _load_schema()

    def summarize_video(
        self,
        transcript_text: str,
        title: str,
        video_date: str | None = None,
    ) -> dict[str, Any]:
        """Call Claude to extract structured analysis from a transcript. Retries on rate limits."""
        date_hint = f" (published {video_date})" if video_date else ""
        user_content = f"Video title: {title}{date_hint}\n\nTranscript:\n{transcript_text}"

        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._client.messages.create(
                    model=config.MODEL_SONNET,
                    max_tokens=4096,
                    system=[
                        {
                            "type": "text",
                            "text": self._system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=[
                        {
                            "name": "record_video_analysis",
                            "description": "Record structured analysis of one video.",
                            "input_schema": self._schema,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tool_choice={"type": "tool", "name": "record_video_analysis"},
                    messages=[{"role": "user", "content": user_content}],
                )
                result = self._extract_tool_result(response)
                log.info(
                    "summarize_video_ok",
                    title=title,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    cache_read=getattr(response.usage, "cache_read_input_tokens", 0),
                )
                return result
            except anthropic.RateLimitError as exc:
                if attempt == self._max_retries:
                    raise
                wait = self._retry_delay * attempt
                log.warning("rate_limit_retry", attempt=attempt, wait=wait, error=str(exc))
                time.sleep(wait)
            except anthropic.APIStatusError as exc:
                if exc.status_code == 529 and attempt < self._max_retries:
                    wait = self._retry_delay * attempt
                    log.warning("api_overloaded_retry", attempt=attempt, wait=wait)
                    time.sleep(wait)
                else:
                    raise

        raise RuntimeError("summarize_video exceeded max retries")  # unreachable

    @staticmethod
    def _extract_tool_result(response: anthropic.types.Message) -> dict[str, Any]:
        for block in response.content:
            if block.type == "tool_use" and block.name == "record_video_analysis":
                return block.input  # type: ignore[return-value]
        raise ValueError(f"No tool_use block in response: {response.content}")
