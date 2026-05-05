# Plan

The plan is organized into four phases. Each phase is independently
useful — meaning if the user stops here, they still get value. **Don't
start the next phase until the current one is in daily use.** That
discipline is what keeps the project from collapsing under its own weight.

Each task has a `[ ]` checkbox. Mark `[x]` when done. Claude Code can
update these directly.

---

## MVP — "I have a free, queryable raw data lake"

**Goal:** End-to-end CLI tool that ingests a channel's full back catalog for free,
without any Claude API calls.

**Definition of done:**
- One command: `python -m src.cli.ingest --channel @SomeStockGuy`
- Pulls every video metadata and fetches transcripts into SQLite. Costs exactly $0.00.
- Resumable: re-running skips already-processed videos.

### Setup
- [ ] Initialize git repo, add Python `.gitignore`
- [x] Set up `pyproject.toml` with dependencies (yt-dlp, youtube-transcript-api, structlog, pytest, click)
- [x] Create `.env.example`
- [x] Add `src/config.py` reading env vars and exposing typed constants
- [x] Verify project runs.

### Data layer
- [x] Define schema in `src/db.py` (videos, chunks tables)
- [x] Add `init_db()`, `upsert_video()`, `get_video()`,
      `list_unprocessed(channel)` helpers
- [x] Write tests for each helper using a temp DB fixture

### YouTube fetching
- [x] `src/youtube.py`: `list_channel_videos(channel)` → returns metadata list
- [x] `src/youtube.py`: `fetch_transcript(video_id)` → returns segments with timestamps
- [x] Handle the "no captions available" case — return None, don't raise
- [x] Test against 2-3 real public videos (small fixture file)

### Pipeline & CLI
- [x] `src/process_video.py`: `process_video_metadata(video_id)` fetching and atomic DB write ONLY.
- [x] `src/cli/ingest.py`: parses `--channel`, lists videos, loops calling ingest
- [x] Progress bar (`rich.progress` or `tqdm`)
- [x] First real run: Ingest all 500+ videos. Cost is $0.

**Estimated time:** one focused weekend.

---

## V1 — "I can search smartly and ask AI on-demand"

**Goal:** Add semantic search (local open-source models) over transcript chunks,
and ONLY use AI to summarize what was found. Cost-effective answers across the archive.

**Definition of done:**
- `python -m src.cli.embed` to build the local knowledge base.
- `python -m src.cli.ask "what's his current view on NVDA?"`
- Query hits local DB, retrieves 3-5 relevant chunks, passes them to Claude Sonnet (Pennies).

### Local Embeddings & ETL
- [ ] Add `sentence-transformers` for local embeddings (e.g. `all-MiniLM-L6-v2`)
- [ ] `src/chunking.py`: split transcript into ~500-token chunks.
- [ ] Create `embeddings` virtual table using `sqlite-vec`
- [ ] Backfill embeddings for all downloaded videos (`src/cli/embed.py`). Costs $0.00.

### Claude On-Demand Integration
- [x] `src/llm.py`: client wrapper with retry
- [x] `src/prompts/system.txt`: stock-analyst system prompt
- [x] `src/prompts/schema.json`: structured-output JSON schema for summarizing queried results

### Retrieval & Chat
- [ ] `src/retrieval.py`: `search(query, k=5)` → top-k chunks by local cosine similarity
- [ ] `src/cli/ask.py`: uses retrieve, sends relevant context to Sonnet, and provides cited answers.
- [ ] Multi-turn — keep last N turns in context

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
