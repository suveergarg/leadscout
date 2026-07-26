"""One-off tool for comparing classifiers against a shared snapshot of real posts.

Fetches a batch of live posts (no keyword pre-filter) into benchmark.db, then classifies
them with Ollama. A separate step (update_benchmark_scores.py) lets any other
classifier - Claude read directly in a chat session, Haiku via the API, etc. - write
its own score/reason into the same rows for a like-for-like comparison.

Fetches via Reddit's multireddit syntax (r/sub1+sub2+.../new/.rss) - combines every
configured subreddit into a SINGLE anonymous-RSS request instead of one per subreddit,
which is what actually matters given the anonymous rate limit allows ~1 request per
reset window shared across all of them. Each entry in a combined feed carries its real
source subreddit via <category label="r/...">, which reddit_client.py's _parse_entry
already reads in preference to the (here, combined) subreddit string passed to
new_posts().

Usage: uv run python scripts/benchmark_classifiers.py
"""

from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from leadscout.classify import OllamaClassifier  # noqa: E402
from leadscout.config import Settings  # noqa: E402
from leadscout.keywords import matched_phrase  # noqa: E402
from leadscout.models import RedditPost  # noqa: E402
from leadscout.reddit_client import RssRedditClient  # noqa: E402

DB_PATH = str(Path(__file__).parent.parent / "benchmark.db")

# Confirmed dead (redirects to a search page, not a real subreddit) - excluded so it
# doesn't break the whole combined request.
_DEAD_SUBREDDITS = {"RECREATIONdotgov"}

# Reddit's RSS honored this in testing; higher values are untested (a limit=250 attempt
# hit a coincidental rate limit before confirming either way).
_FETCH_LIMIT = 100

_SCHEMA = """
CREATE TABLE IF NOT EXISTS classifications (
    post_id TEXT PRIMARY KEY,
    subreddit TEXT,
    title TEXT,
    permalink TEXT,
    author TEXT,
    created_utc REAL,
    body_snippet TEXT,
    keyword_matched TEXT,
    ollama_score REAL,
    ollama_reason TEXT,
    claude_score REAL,
    claude_reason TEXT,
    haiku_score REAL,
    haiku_reason TEXT
);
"""


def fetch_and_store(conn: sqlite3.Connection, settings: Settings) -> None:
    live_subreddits = [s for s in settings.subreddits if s not in _DEAD_SUBREDDITS]
    combined = "+".join(live_subreddits)
    client = RssRedditClient(settings.user_agent)
    try:
        posts = client.new_posts(combined, limit=_FETCH_LIMIT)
    except Exception as exc:  # noqa: BLE001 - report and leave whatever's already stored
        print(f"failed to fetch combined feed ({combined}): {exc}")
        client.close()
        return
    for post in posts:
        phrase = matched_phrase(post.title, post.body_snippet)
        conn.execute(
            """INSERT OR IGNORE INTO classifications
               (post_id, subreddit, title, permalink, author, created_utc,
                body_snippet, keyword_matched)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                post.post_id,
                post.subreddit,
                post.title,
                post.permalink,
                post.author,
                post.created_utc,
                post.body_snippet,
                phrase,
            ),
        )
    conn.commit()
    client.close()
    counts = Counter(p.subreddit for p in posts)
    print(f"fetched {len(posts)} posts across {len(counts)} subreddits:")
    for sub, count in counts.most_common():
        print(f"  r/{sub}: {count}")


def classify_with_ollama(conn: sqlite3.Connection, settings: Settings) -> None:
    if not settings.ollama_url:
        print("LEADSCOUT_OLLAMA_URL not set - skipping Ollama classification")
        return
    classifier = OllamaClassifier(settings.ollama_url, settings.ollama_model)
    rows = conn.execute(
        "SELECT post_id, subreddit, title, permalink, author, created_utc, body_snippet "
        "FROM classifications WHERE ollama_score IS NULL"
    ).fetchall()
    for post_id, subreddit, title, permalink, author, created_utc, body_snippet in rows:
        post = RedditPost(
            post_id=post_id,
            subreddit=subreddit,
            title=title,
            permalink=permalink,
            author=author,
            created_utc=created_utc,
            body_snippet=body_snippet,
        )
        result = classifier.classify(post)
        conn.execute(
            "UPDATE classifications SET ollama_score = ?, ollama_reason = ? WHERE post_id = ?",
            (result.score, result.reason, post_id),
        )
        conn.commit()
        print(f"[ollama] {post_id} score={result.score:.2f} {result.reason}")


if __name__ == "__main__":
    settings = Settings()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    conn.commit()
    fetch_and_store(conn, settings)
    classify_with_ollama(conn, settings)
    conn.close()
    print(f"\nDone. Benchmark data in {DB_PATH}")
