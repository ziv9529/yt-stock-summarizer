# YouTube Stock-Analyst Summarizer

A personal pipeline that ingests a stock-focused YouTuber's video
archive, extracts structured insights with Claude, and stores them in a
queryable local SQLite database. Later phases add semantic search, a
chat interface, and live notifications on new uploads.

Runs locally, free except for Claude API usage (a few dollars to
backfill a couple hundred videos).

## Status

Pre-MVP. See `docs/plan.md` for the roadmap and `CLAUDE.md` for the
project conventions Claude Code follows.

## Quick start (once MVP is built)

```bash
cp .env.example .env       # add your ANTHROPIC_API_KEY
pip install -e .
python -m src.cli.backfill --channel @SomeStockGuy --limit 5
sqlite3 data/archive.db "SELECT title, sentiment_score FROM videos JOIN summaries USING(video_id) ORDER BY published_at DESC LIMIT 10;"
```

## Project layout

- `CLAUDE.md` — instructions Claude Code reads at the start of every session
- `docs/architecture.md` — system design and data flow
- `docs/plan.md` — phased roadmap (MVP → V1 → V2 → V3)
- `docs/prompts.md` — Claude system prompts and structured-output schema
- `docs/decisions.md` — architectural decision log
- `src/` — implementation (populated as work progresses)
