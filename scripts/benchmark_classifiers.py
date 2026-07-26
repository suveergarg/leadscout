"""One-off tool for comparing classifiers against a shared snapshot of real posts.

Fetches a batch of live posts (no keyword pre-filter) into benchmark.db, then classifies
them with Ollama. A separate step (update_benchmark_scores.py) lets any other
classifier - Claude read directly in a chat session, Haiku via the API, etc. - write
its own score/reason into the same rows for a like-for-like comparison.

Usage: uv run python scripts/benchmark_classifiers.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from leadscout.classify import OllamaClassifier  # noqa: E402
from leadscout.config import Settings  # noqa: E402
from leadscout.keywords import matched_phrase  # noqa: E402
from leadscout.models import RedditPost  # noqa: E402
from leadscout.reddit_client import RssRedditClient  # noqa: E402

DB_PATH = str(Path(__file__).parent.parent / "benchmark.db")

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
    client = RssRedditClient(settings.user_agent)
    for subreddit in settings.subreddits:
        try:
            posts = client.new_posts(subreddit, limit=settings.posts_per_subreddit)
        except Exception as exc:  # noqa: BLE001 - one bad subreddit must not kill the run
            print(f"failed to fetch r/{subreddit}: {exc}")
            continue
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
        print(f"r/{subreddit}: fetched {len(posts)} posts")
    client.close()


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
