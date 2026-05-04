# Prompts

This file is the source of truth for Claude prompts and structured-output
schemas. **Edit prompts here, then sync them into `src/prompts/` files.**
Don't hand-edit prompts inside Python source — they belong in `.txt` and
`.json` files imported by `llm.py`, so changes are diffable.

## Why structured output

We use Claude's tool-use feature to force JSON output that matches a
defined schema. This is more reliable than asking for "JSON in a code
block" and parsing free text. The pattern:

1. Define a tool called `record_video_analysis` with the schema below.
2. Pass it as `tools=[...]` and `tool_choice={"type": "tool", "name": "record_video_analysis"}`.
3. Claude returns a `tool_use` block whose `input` field already matches
   the schema. Validate with `pydantic` for safety, then persist.

Reference: https://docs.claude.com/en/docs/build-with-claude/tool-use

## Main system prompt — stock-analyst summarizer

This goes in `src/prompts/system.txt`. Wrap it in prompt caching so we
don't pay for it on every video.

```
You are an expert financial analyst summarizing videos from a YouTube
channel that focuses on stocks, markets, and investing.

Your job is to extract structured, queryable insights from a single
video's transcript. You are talking to one user — the channel's regular
viewer — who wants to keep track of what the YouTuber has said over time
without re-watching every video.

Principles:

- Be precise about who is making each claim. The YouTuber is "the
  speaker". Distinguish between the speaker's own views, views they are
  reporting from someone else, and views they are arguing against.
- Capture stance with care. Bullish/bearish/neutral applies only when
  the speaker is making a directional call on a specific security or
  sector. Don't mark a stance from a passing mention.
- Preserve uncertainty. If the speaker says "I think" or "maybe", record
  that — don't promote a hedge to a hard call.
- Always include a timestamp for any claim that maps to a specific
  moment. The transcript you receive includes seconds; pass them through
  in `mm:ss` format.
- If the video is not actually about stocks (e.g. lifestyle vlog,
  channel update), set `is_finance_content` to false and keep other
  fields minimal.

Output via the `record_video_analysis` tool. Do not return free text.
```

## Structured output schema

This goes in `src/prompts/schema.json` and is loaded by `llm.py` as the
tool input schema.

```json
{
  "type": "object",
  "required": [
    "is_finance_content",
    "tldr",
    "key_points",
    "tickers_mentioned",
    "topics",
    "sentiment_score"
  ],
  "properties": {
    "is_finance_content": {
      "type": "boolean",
      "description": "True if the video meaningfully discusses stocks, markets, or investing. False for off-topic content."
    },
    "tldr": {
      "type": "string",
      "description": "1-2 sentence summary of the video's main argument or content."
    },
    "key_points": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["timestamp", "point"],
        "properties": {
          "timestamp": { "type": "string", "description": "mm:ss or hh:mm:ss" },
          "point": { "type": "string", "description": "One sentence." }
        }
      }
    },
    "tickers_mentioned": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["symbol", "stance"],
        "properties": {
          "symbol": { "type": "string", "description": "Ticker, uppercase. e.g. NVDA, BRK.B" },
          "stance": { "type": "string", "enum": ["bullish", "bearish", "neutral", "mentioned_only"] },
          "price_target": { "type": ["string", "null"], "description": "If the speaker gave one." },
          "time_horizon": { "type": ["string", "null"], "enum": ["short_term", "medium_term", "long_term", null] },
          "rationale": { "type": "string", "description": "Why the speaker holds this stance." },
          "timestamp": { "type": ["string", "null"] }
        }
      }
    },
    "topics": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Free-form topic tags. e.g. 'AI infrastructure', 'Fed policy', 'earnings'."
    },
    "macro_views": {
      "type": ["string", "null"],
      "description": "Speaker's views on macro factors (rates, inflation, recession) if any."
    },
    "sentiment_score": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10,
      "description": "Overall market sentiment of the video. 1=very bearish, 10=very bullish."
    },
    "notable_quotes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "timestamp": { "type": "string" },
          "quote": { "type": "string", "description": "Verbatim, max 25 words." }
        }
      }
    }
  },
  "additionalProperties": false
}
```

## Q&A system prompt (V1)

This goes in `src/prompts/qa.txt`. Used by `cli/ask.py` for RAG over the
archive.

```
You are answering questions about a stock-focused YouTube channel's
content based on transcript excerpts retrieved from a database.

The user is the channel's regular viewer trying to recall or aggregate
what the speaker has said over time.

Rules:

- Only use information from the provided <chunks>. If the chunks don't
  contain the answer, say so plainly. Don't speculate, don't fill in.
- Cite every claim with the video title and timestamp from the chunk
  it came from. Format: [Video Title @ mm:ss].
- When summarizing across multiple videos, group findings chronologically
  if the user is asking about a position over time.
- If the speaker has changed their view, surface that explicitly: "In
  March he was bullish ... by August he had reversed."
- Distinguish between the speaker's own views and views they were
  reporting or critiquing.
```

## Prompt caching

When calling the API, mark the system prompt and the tool schema as
cacheable. Anthropic charges full price for the first call but ~10% for
subsequent calls within the cache TTL. Across hundreds of videos this
saves real money. See https://docs.claude.com/en/docs/build-with-claude/prompt-caching.

In `llm.py`, the call should look like:

```python
client.messages.create(
    model=config.MODEL_SONNET,
    system=[
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
    ],
    tools=[
        {
            "name": "record_video_analysis",
            "description": "Record structured analysis of one video.",
            "input_schema": SCHEMA,
            "cache_control": {"type": "ephemeral"},
        }
    ],
    tool_choice={"type": "tool", "name": "record_video_analysis"},
    messages=[{"role": "user", "content": user_content}],
    max_tokens=4096,
)
```

## Iteration log

Whenever the prompt or schema changes meaningfully, append a dated note
here describing what changed and why. Keeps the history visible without
needing to dig through git.

- *YYYY-MM-DD* — initial version, MVP.
