# Decisions

A running log of architectural decisions, in newest-first order. Each
entry is a tiny ADR — context, decision, consequence. When you change
your mind later, don't rewrite history; add a new entry that supersedes
the old one.

The discipline of writing these down forces you to actually decide,
instead of drifting. If you can't articulate why X over Y, you don't
have a decision yet — you have a default.

---

## Template

```
## YYYY-MM-DD — Title

**Context.** What's the situation that made this come up?

**Decision.** What did we pick?

**Consequence.** What does this make easy / hard going forward?
What did we give up?

**Status.** Active / Superseded by [date] / Reverted.
```

---

## YYYY-MM-DD — Use SQLite for MVP storage

**Context.** Need a place to store video metadata, transcripts, and
structured Claude output. The system is single-user and runs locally.

**Decision.** SQLite, with the schema applied idempotently from
`src/db.py`. No ORM — handwritten queries with `sqlite3` stdlib.

**Consequence.** Zero setup, ships with Python, the whole DB is one
file the user can copy or delete. Ad-hoc queries possible from the
sqlite3 CLI. Migration to Postgres later means rewriting `db.py`, but
the rest of the code stays put because all DB access is funneled
through that module.

**Status.** Active.

---

## YYYY-MM-DD — Sonnet 4.6 as default model

**Context.** Need to pick the Claude model for video summarization.
Options: Haiku 4.5 (cheap, fast, less capable), Sonnet 4.6 (balanced),
Opus 4.7 (most capable, expensive).

**Decision.** Sonnet 4.6 (`claude-sonnet-4-6`) for summarization. Haiku
4.5 (`claude-haiku-4-5-20251001`) for any cleaning/preprocessing pass.
Opus only if a real quality problem appears.

**Consequence.** ~$3 per million input tokens. With prompt caching
enabled, processing ~200 videos of ~30 min transcripts costs a few
dollars total. Quality is high enough for structured extraction. We
revisit if outputs are noticeably wrong on real videos.

**Status.** Active.

---

## YYYY-MM-DD — Tool-use for structured output

**Context.** Need reliable JSON from Claude. Options: ask for JSON in
the prompt and parse, use prefilling, use tool-use.

**Decision.** Tool-use with a single tool (`record_video_analysis`) and
forced `tool_choice`. The tool's input schema *is* the contract.

**Consequence.** No regex parsing, no broken JSON, schema violations
fail loudly at the API boundary instead of silently downstream. Slight
extra prompt complexity. Schema lives in one file.

**Status.** Active.

---

## YYYY-MM-DD — Backfill before live tracking

**Context.** Two ways to populate the DB: backfill the existing archive,
or only process videos uploaded from now forward. The user explicitly
asked to focus on past content.

**Decision.** Build backfill (MVP) first. Live tracking is V2 and
reuses the same `process_video()` function — just triggered by a
webhook instead of a CLI loop.

**Consequence.** Immediate value from the existing archive. Live
tracking later is additive, not a redesign.

**Status.** Active.
