# Architecture

## What this system is

A backfill-first pipeline that turns a YouTube channel's video archive into
a structured, queryable knowledge base of stock-related content. Later,
the same pipeline supports semantic search, a chat interface, and live
notification on new uploads.

The architecture is shaped by one observation: backfilling past videos and
processing new ones are the same operation triggered differently. Every
ingestion path eventually calls the same `process_video(video_id)`
function. Get that function right and the rest is plumbing.

## Data flow

```
Trigger → Fetcher → Processor → Storage → Consumption
```

**Trigger** decides which videos to process. Three kinds:

- *Backfill* — a script that lists every video on a channel and queues
  unprocessed ones (MVP).
- *Manual* — process a single video by URL on demand (V1).
- *Live webhook* — PubSubHubbub notification when the channel uploads
  (V2). PubSubHubbub is YouTube's free push system; no quota, no polling.

**Fetcher** pulls raw inputs:

- `yt-dlp` lists videos and returns metadata (title, description,
  published date, duration).
- `youtube-transcript-api` returns the transcript with per-segment
  timestamps. If unavailable, log and skip — Whisper fallback is V3.

**Processor** is the core:

1. Optional cleaning pass with Haiku — adds punctuation, fixes
   homophone errors common in auto-captions ("nvidya" → "Nvidia").
2. Main summarization pass with Sonnet — returns a single JSON object
   matching the schema in `docs/prompts.md`. The schema is enforced via
   tool-use (preferred) or prefilling.
3. Persistence — write metadata, transcript, and parsed structured fields
   to SQLite atomically. If any step fails, leave the row absent so the
   backfill can retry it cleanly on the next run.

**Storage** is SQLite with three tables:

- `videos` — one row per video, holds metadata + raw transcript text.
- `summaries` — one row per video, holds the structured Claude output.
- `chunks` — one row per ~500-token transcript segment, with timestamps.
  Embeddings get added in V1 when we wire up `sqlite-vec`.

Schema lives in `src/db.py` as a single `SCHEMA` constant applied
idempotently with `CREATE TABLE IF NOT EXISTS`.

**Consumption** is how the user gets value out:

- *MVP* — SQL queries directly against the DB. The user (you) writes
  ad-hoc queries to answer questions like "every NVDA mention this year".
- *V1* — semantic search via embeddings, plus a CLI that does RAG over
  transcript chunks for fuzzy questions ("what did he say about geopolitical
  risk").
- *V2* — push notifications on new uploads via Telegram bot.
- *V3* — web UI over the same data.

## Module layout

```
src/
├── __init__.py
├── config.py          # paths, model strings, API keys from env
├── db.py              # schema, queries, transactions
├── llm.py             # Claude client wrapper: retries, caching, models
├── youtube.py         # yt-dlp + transcript-api wrappers
├── process_video.py   # the core pipeline, reused everywhere
├── prompts/
│   ├── __init__.py
│   ├── system.txt     # main analyst system prompt
│   └── schema.json    # structured output JSON schema
└── cli/
    ├── __init__.py
    ├── backfill.py    # MVP entry point
    └── ask.py         # V1 chat entry point
```

The CLI scripts are *thin*. Their job is parse args → call into `src/`
modules → format output. All real logic lives in the modules.

## Why these choices

**SQLite, not Postgres.** Single-user local tool. SQLite is zero-setup,
embeds in the Python file, ships with the language. When the user upgrades
to Supabase later, the DAL lives in `db.py` so the swap is contained.

**`youtube-transcript-api`, not the YouTube Data API for captions.** The
official API doesn't return caption text directly without OAuth dance and
quota cost; the unofficial library reads the same auto-generated captions
YouTube serves to its own player. Free, no quota.

**`yt-dlp`, not the YouTube Data API for listing.** `yt-dlp` lists every
video on a channel without an API key. The Data API costs quota per page
and requires OAuth setup. We only fall back to the Data API if a future
feature genuinely needs it.

**Tool-use for structured output, not free-text JSON parsing.** Claude
returns a tool call with the exact schema we define. No regex, no broken
JSON, no parsing failures. Falls through cleanly to validation in Python.

**Sonnet 4.6 as default, Haiku 4.5 for prep.** Sonnet is the
quality/cost sweet spot for analysis. Haiku is ~3x cheaper for the
mechanical cleaning step where quality requirements are lower. Two-tier
routing keeps the bill in single digits per month even with hundreds of
videos.

**Prompt caching on the system prompt.** Saves ~90% on input tokens for
the system prompt, which is identical across every video. One config
flag in `llm.py`, big bill reduction.

## Open questions

These are intentionally deferred until we have data:

- *How long should chunks be for retrieval?* — tune in V1 with real
  queries against a real corpus.
- *Do we re-process when the YouTuber updates a description?* — probably
  no for MVP; revisit if it bites us.
- *Multi-channel naming/scoping?* — wait until we want a second channel.
  Premature multi-tenancy is a known pit.
