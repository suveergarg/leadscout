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
`LEADSCOUT_REDDIT_CLIENT_ID` / `LEADSCOUT_REDDIT_CLIENT_SECRET` in `.env` for the real PRAW-backed
client. As of 2026, new Reddit app registrations require manual approval under Reddit's
Responsible Builder Policy (a multi-week, ticket-based review) — see
`support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy`.

**Without credentials, leadscout automatically falls back to `RssRedditClient`** (see
`reddit_client.py`), which reads each subreddit's public `new` Atom feed
(`reddit.com/r/SUBREDDIT/new/.rss`) directly — no app, no approval needed, since this endpoint
was never part of the priced/gated API surface (unlike `.json` scraping, which is blocked
outright). It's meant to unblock local development and cover the approval-wait period, not as a
permanent replacement:

- It's tightly, and anonymously, rate-limited — confirmed live, the per-IP bucket allows
  roughly one request before `x-ratelimit-remaining` hits 0, refilling after
  `x-ratelimit-reset` seconds. `RssRedditClient` honors those headers and blocks until the
  bucket refills, so a full pass over ~10 subreddits can take several minutes — fine inside a
  15-minute poll interval, but don't expect it to be fast.
- The limit appeared to be shared across *all* anonymous traffic from the same IP, not scoped
  per subreddit or per process — so other anonymous Reddit traffic from the same machine can
  eat into the same budget.
- A 429 on one subreddit is non-fatal: `poll_once` logs it and moves on, and that subreddit gets
  retried on the next poll cycle.

Switch back to the PRAW client the moment your Reddit app is approved — it's what
`build_reddit_client` returns automatically once both credential env vars are set.

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
