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
Trigger → Ingester → Storage → Local ETL/RAG → Consumption (On-Demand AI)
```

**Trigger** decides which videos to process. Three kinds:

- *Backfill* — a script that lists every video on a channel and queues
  unprocessed ones for metadata and transcript fetching (MVP).
- *Manual* — process a single video by URL on demand (V1).
- *Live webhook* — PubSubHubbub notification when the channel uploads
  (V2). PubSubHubbub is YouTube's free push system; no quota, no polling.

**Ingester** pulls raw inputs (100% FREE):

- `yt-dlp` lists videos and returns metadata (title, description,
  published date, duration).
- `youtube-transcript-api` returns the transcript with per-segment
  timestamps. If unavailable, log and skip.

**Storage** is SQLite with three primary tables:

- `videos` — one row per video, holds metadata + raw transcript text.
- `chunks` — one row per ~500-token transcript segment, with timestamps.
  Embeddings get added using a local open-source model (e.g., `all-MiniLM-L6-v2`) via `sqlite-vec`.

**Local ETL/RAG** is the free preprocessing layer:

1. Runs open-source local embeddings on the text chunks.
2. Runs basic Python regex/keyword extractors to find tickers locally before AI is used.

**Consumption (On-Demand AI)** is how the user gets value out (PENNIES):

Instead of paying to summarize the entire channel upfront, AI is applied *just-in-time*.
- You query your local database/RAG index for a topic or ticker (e.g. "NVDA").
- The database returns the top 3-5 most matched transcript chunks.
- Only these specific chunks are sent to Claude (Sonnet) to generate the final summarized answer.

## Module layout

```
src/
├── __init__.py
├── config.py          # paths, model strings, API keys from env
├── db.py              # schema, queries, transactions
├── llm.py             # Claude client wrapper for on-demand analysis
├── youtube.py         # yt-dlp + transcript-api wrappers
├── chunking.py        # local ETL, regex extractors, and open-source embeddings
├── process_video.py   # fetches and stores raw video data
├── prompts/
│   ├── __init__.py
│   ├── system.txt     # main analyst system prompt for on-demand search
│   └── schema.json    # structured output JSON schema
└── cli/
    ├── __init__.py
    ├── ingest.py      # New MVP entry: 100% free bare-metal fetching
    ├── embed.py       # Local ETL / Chunking entry
    └── ask.py         # On-Demand AI querying tool
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
