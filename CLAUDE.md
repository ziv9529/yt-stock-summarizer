# YouTube Stock-Analyst Summarizer

Personal tool that ingests a stock-focused YouTuber's video archive, summarizes
each video into structured insights (tickers, stances, targets, sentiment),
and stores them in a queryable local database. Later phases add semantic
search over transcripts, a chat interface, and live tracking of new uploads.

This is a learning project and a personal tool — not a product. Optimize for
clarity, low operational cost, and being able to explain every line.

## Stack

- Python 3.11+
- `yt-dlp` for channel listing and metadata
- `youtube-transcript-api` for captions
- `anthropic` SDK for Claude calls
- SQLite (stdlib) for storage; `sqlite-vec` later for embeddings
- `pytest` for tests, `structlog` for logging
- No cloud services in MVP — runs locally on the user's laptop

## Models

Use these exact strings (verified current as of May 2026):

- `claude-haiku-4-5-20251001` — transcript cleaning, simple extraction
- `claude-sonnet-4-6` — main summarization and Q&A (default)
- `claude-opus-4-7` — only when reasoning quality genuinely matters

Never use unversioned aliases like `claude-sonnet-latest` in code. Pin
versions in a config constant so upgrades are a one-line change.

## Conventions

- Type hints on every function signature
- `pathlib.Path`, never `os.path`
- All Claude API calls go through `src/llm.py` (single chokepoint for
  retries, prompt caching, logging, model selection)
- All DB access goes through `src/db.py` — no raw SQL in business logic
- Secrets only in `.env`, never committed; `.env.example` lists every
  variable the project reads
- Small commits, one logical change each, prefixed with the phase
  (e.g. `MVP: add transcript fetcher`)

## Workflow rules

1. Before adding a feature, confirm it belongs to the current phase.
   See `@docs/plan.md`. Resist scope creep.
2. For multi-file changes, use plan mode first. Show the plan, wait for
   approval, then execute.
3. Write the test, run it, then call the work done. Never claim something
   works without running it.
4. After a real architectural decision, update `@docs/decisions.md` in the
   same session.
5. Use `/clear` between phases to keep the context window healthy.

## Key files

- `@docs/architecture.md` — system design and data flow. Read before
  changing the structure of `src/`.
- `@docs/plan.md` — phased roadmap (MVP → V1 → V2 → V3) with checklists.
- `@docs/prompts.md` — Claude system prompts and the structured-output
  schema. Edit prompts here, not inline in code.
- `@docs/decisions.md` — short ADRs explaining why we chose X over Y.
- `src/process_video.py` — the core video-processing function reused by
  every trigger (backfill, manual, live).

## Don'ts

- Don't add Postgres, Redis, Docker, or any cloud service in MVP.
  SQLite + a script is the whole stack.
- Don't fetch transcripts via the official YouTube Data API. Use
  `youtube-transcript-api` (free, no quota).
- Don't write summaries directly into the prompt as f-strings — use the
  templates in `src/prompts/` so they stay diffable.
- Don't run a backfill against the live channel during testing. Use the
  fixture set in `tests/fixtures/` until the prompt is stable.
