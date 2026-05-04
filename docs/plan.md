# Plan

The plan is organized into four phases. Each phase is independently
useful — meaning if the user stops here, they still get value. **Don't
start the next phase until the current one is in daily use.** That
discipline is what keeps the project from collapsing under its own weight.

Each task has a `[ ]` checkbox. Mark `[x]` when done. Claude Code can
update these directly.

---

## MVP — "I have a queryable archive"

**Goal:** End-to-end CLI tool that ingests a channel's full back catalog
and lets the user run SQL queries against the structured summaries.

**Definition of done:**
- One command: `python -m src.cli.backfill --channel @SomeStockGuy`
- Pulls every video, fetches transcripts, calls Claude, writes to SQLite
- Resumable: re-running skips already-processed videos
- The user can answer "every NVDA mention with bullish stance this year"
  with a single SQL query

### Setup
- [ ] Initialize git repo, add Python `.gitignore`
- [x] Set up `pyproject.toml` with dependencies (yt-dlp,
      youtube-transcript-api, anthropic, structlog, pytest, click)
- [x] Create `.env.example` with `ANTHROPIC_API_KEY=`
- [x] Add `src/config.py` reading env vars and exposing typed constants
- [x] Pin model strings in config (sonnet `claude-sonnet-4-6`,
      haiku `claude-haiku-4-5-20251001`)
- [x] Verify project runs: `python -c "from src import config; print(config.ANTHROPIC_API_KEY[:6])"`

### Data layer
- [x] Define schema in `src/db.py` (videos, summaries, chunks tables)
- [x] Add `init_db()`, `upsert_video()`, `get_video()`,
      `list_unprocessed(channel)` helpers
- [x] Write tests for each helper using a temp DB fixture

### YouTube fetching
- [x] `src/youtube.py`: `list_channel_videos(channel)` → returns metadata list
- [x] `src/youtube.py`: `fetch_transcript(video_id)` → returns segments with timestamps
- [x] Handle the "no captions available" case — return None, don't raise
- [x] Test against 2-3 real public videos (small fixture file)

### Claude integration
- [x] `src/llm.py`: client wrapper with retry, prompt caching, model selection
- [x] `src/prompts/system.txt`: stock-analyst system prompt
- [x] `src/prompts/schema.json`: structured-output JSON schema
- [x] `src/llm.py`: `summarize_video(transcript, metadata)` → validated dict
- [x] Test with one cached real transcript; assert schema fields populated

### Pipeline
- [x] `src/process_video.py`: `process_video(video_id)` orchestrates fetch → clean → summarize → persist
- [x] Atomic write — if Claude call fails, no partial row remains
- [x] Idempotent — re-running on a processed video is a no-op

### CLI
- [x] `src/cli/backfill.py`: parses `--channel`, lists videos, loops calling `process_video`
- [x] Progress bar (`rich.progress` or `tqdm`)
- [x] Resume support — list_unprocessed handles it
- [x] `--limit N` flag for testing on a subset

### First real run
- [x] Run on the user's actual chosen channel with `--limit 5`
- [x] Inspect summaries by hand — are tickers extracted? Stances correct?
- [x] Iterate on system prompt until the output is genuinely useful
- [x] Run full backfill
- [x] Write 5 example SQL queries in `docs/queries.md` and confirm they answer real questions

**Estimated time:** one focused weekend (8–12 hours for someone comfortable with Python).

---

## V1 — "I can ask questions across the whole archive"

**Goal:** Add semantic search over transcript chunks and a chat-style CLI
that does RAG to answer fuzzy questions across all videos.

**Definition of done:**
- `python -m src.cli.ask "what's his current view on AI infrastructure?"`
- Answer cites which videos and timestamps it came from
- User can have a follow-up turn that maintains context

### Embeddings
- [ ] Pick embedding provider (Voyage AI free tier or OpenAI text-embedding-3-small)
      → record decision in `docs/decisions.md`
- [ ] Add embedding dependency, set up API key in `.env.example`
- [ ] `src/llm.py`: `embed(texts: list[str]) → list[list[float]]`
- [ ] Install `sqlite-vec` extension; add `embeddings` virtual table to schema
- [ ] Backfill embeddings for all chunks already in DB

### Chunking
- [ ] `src/chunking.py`: split transcript into ~500-token chunks preserving timestamps
- [ ] Run chunker over existing transcripts, store in `chunks` table
- [ ] Test that timestamps round-trip correctly

### Retrieval
- [ ] `src/retrieval.py`: `search(query, k=8)` → top-k chunks by cosine similarity
- [ ] `src/retrieval.py`: `build_context(chunks)` → formatted string with citations
- [ ] Test that obvious queries hit obvious chunks

### Chat CLI
- [ ] `src/cli/ask.py`: REPL loop, sends user question + retrieved context to Sonnet
- [ ] Multi-turn — keep last N turns in context
- [ ] Format responses with `[video title @ MM:SS]` citations
- [ ] Conversation history saved to SQLite for later review

### Evaluation
- [ ] Write 10 representative questions in `tests/eval_questions.md`
- [ ] Manually grade answers against the actual videos
- [ ] Iterate on prompts and retrieval k until quality is acceptable

**Estimated time:** one weekend.

---

## V2 — "I get pinged when there's a new video worth knowing about"

**Goal:** Live tracking. New uploads on tracked channels trigger automatic
processing and a Telegram (or Discord) notification with the summary —
but only if the content crosses a relevance threshold.

**Definition of done:**
- A YouTuber the user tracks uploads a video → within ~75 minutes the
  user gets a Telegram message with the structured summary, only if a
  high-priority finding is present (specific ticker call, score above
  threshold, etc.)
- The whole thing runs on free-tier Cloudflare Workers — no VPS

### PubSubHubbub
- [ ] `src/notify/subscribe.py`: send subscription request to YouTube hub
- [ ] Endpoint that handles the verification challenge
- [ ] Endpoint that handles incoming notifications, with secret verification
- [ ] Dedupe — check if video_id already processed before queuing
- [ ] Auto-renewal — subscriptions expire every ~5 days

### Hosting
- [ ] Decide: Cloudflare Workers (TS rewrite of the trigger layer) or
      keep Python on a free Fly.io VM. Record decision.
- [ ] Deploy chosen runtime, expose webhook URL
- [ ] Configure secret used for hub verification

### Delayed processing
- [ ] Schedule processing 1 hour after upload (comments need time to accumulate)
- [ ] Optional: second pass at 24 hours for richer comment analysis

### Notifications
- [ ] Set up Telegram bot, store bot token + chat ID in env
- [ ] `src/notify/telegram.py`: send formatted summary message
- [ ] Threshold logic: only send if `sentiment_score >= X` OR
      `tickers_mentioned` contains a watched symbol

### Operations
- [ ] Logging that the user can actually inspect
- [ ] Health check / dead-man's-switch — alert if no notifications in N days
- [ ] Multi-channel support: list of channels in DB, subscribe each

**Estimated time:** two weekends.

---

## V3 — "I have a real interface for this"

**Goal:** A simple web UI for browsing summaries, filtering by ticker /
date / stance, and using the chat interface from a phone.

This is the "make it nice" phase. Only build it if the user is using the
CLI version daily and feels limited by it.

### UI scope
- [ ] Migrate DB to Supabase (free tier) so the web app can read it
- [ ] Next.js + Tailwind + shadcn/ui frontend
- [ ] Video list page with filters (date range, ticker, sentiment range)
- [ ] Video detail page showing summary, key points with timestamps,
      links to the YouTube video
- [ ] Chat page with the same RAG endpoint, mobile-friendly
- [ ] Auth: Supabase Auth or Clerk, single-user

### Polish
- [ ] Whisper fallback for videos without auto-captions
- [ ] Re-process flag — re-run processing on a video with updated prompt
- [ ] Export summaries to Markdown / Notion

**Estimated time:** open-ended; only start if motivated.

---

## Phase boundaries

A phase is done when:

1. Every checkbox above is `[x]`
2. The user has used the new capability for at least 3 days without
   needing to fix something
3. Lessons learned are written into `docs/decisions.md`

If you're tempted to skip ahead, write down *why* in `docs/decisions.md`
first — the act of explaining the deviation often reveals it's a bad idea.
