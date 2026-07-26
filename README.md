# leadscout

Reddit lead-gen scanner for availwatch. Polls a fixed list of camping/permit subreddits,
keyword-filters new posts for "frustrated with sold-out availability" signals, scores the
survivors with an LLM, and stores hits in SQLite for review in a local dashboard.

## Setup

```bash
cd leadscout
uv sync --extra dev
cp .env.example .env
```

Register a "script" app at https://www.reddit.com/prefs/apps and fill in
`LEADSCOUT_REDDIT_CLIENT_ID` / `LEADSCOUT_REDDIT_CLIENT_SECRET` in `.env` — nothing works without
this (no-auth `.json` scraping is blocked outright by Reddit's edge).

`ANTHROPIC_API_KEY` (or `LEADSCOUT_OLLAMA_URL` for a local model) is optional: without either,
every keyword match is stored with a flat 0.5 score instead of a real LLM judgment.

## Run

```bash
uv run leadscout poll-once   # single pass, then exit — good for trying it out
uv run leadscout run         # long-running loop, polls every LEADSCOUT_POLL_INTERVAL_SECONDS
uv run leadscout serve       # dashboard at http://127.0.0.1:8100
```

## Test

```bash
uv run pytest -q
```
