"""One-off tool for comparing classifiers against a shared snapshot of real posts.

Fetches a batch of live posts (no keyword pre-filter) into benchmark.db, then classifies
them with Ollama. A separate step lets any other classifier - Claude read directly in a
chat session, Haiku via the API, etc. - write its own score/reason into the same rows
for a like-for-like comparison.

Fetches via Reddit's multireddit syntax (r/sub1+sub2+.../SORT/.rss) - combines every
configured subreddit into a SINGLE anonymous-RSS request instead of one per subreddit,
which is what actually matters given the anonymous rate limit allows ~1 request per
reset window shared across all of them. Each entry carries its real source subreddit
via <category label="r/...">, which reddit_client.py's _parse_entry already reads in
preference to the (here, combined) subreddit string passed to new_posts().

A single request caps at 100 entries (confirmed live, tested up to limit=500) and
"new" only goes so deep before running out of recent content, so reaching a large
target count sweeps multiple sort orders (new/hot/rising/top+controversial across
several time windows) and paginates each with `after=<last fullname>` (confirmed live:
~1 post of overlap per 100) until that sort's listing runs dry (an empty or
all-duplicate page) or a per-sort safety cap is hit.

Usage: uv run python scripts/benchmark_classifiers.py [target_count]
"""

from __future__ import annotations

import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from leadscout.classify import OllamaClassifier  # noqa: E402
from leadscout.config import Settings  # noqa: E402
from leadscout.keywords import matched_phrase  # noqa: E402
from leadscout.models import RedditPost  # noqa: E402
from leadscout.reddit_client import RssRedditClient, combined_subreddits  # noqa: E402

DB_PATH = str(Path(__file__).parent.parent / "benchmark.db")

# Confirmed live: Reddit's RSS caps a response at exactly 100 entries regardless of the
# limit requested (tested up to 500) or how many subreddits are combined.
_FETCH_LIMIT = 100

# Each is (sort, time_filter). "new"/"hot"/"rising" ignore time_filter. Ordered
# richest-first so an early stop (target count reached) keeps the most useful mix.
_SORTS: list[tuple[str, str | None]] = [
    ("new", None),
    ("top", "all"),
    ("top", "year"),
    ("top", "month"),
    ("controversial", "all"),
    ("top", "week"),
    ("hot", None),
    ("rising", None),
    ("top", "day"),
]

# Stop a single sort's pagination after this many consecutive pages that add nothing
# new (the listing has run dry) - independent of the safety cap below.
_MAX_EMPTY_PAGES = 2
# Hard ceiling on pages per sort so a bug (e.g. `after` not advancing) can't loop
# forever - 30 pages is ~3000 posts, comfortably past what any single sort/time-window
# actually contains for this niche.
_MAX_PAGES_PER_SORT = 30

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


def _store_posts(conn: sqlite3.Connection, posts: list[RedditPost]) -> int:
    """Returns how many were genuinely new (INSERT OR IGNORE against post_id)."""
    before = conn.total_changes
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
    return conn.total_changes - before


def fetch_and_store(conn: sqlite3.Connection, settings: Settings, target_count: int) -> None:
    combined = combined_subreddits(settings.subreddits)
    client = RssRedditClient(settings.user_agent)
    total_in_db = conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]

    for sort, time_filter in _SORTS:
        if total_in_db >= target_count:
            break
        after: str | None = None
        empty_pages = 0
        sort_new = 0
        for page in range(_MAX_PAGES_PER_SORT):
            try:
                posts = client.new_posts(
                    combined, limit=_FETCH_LIMIT, sort=sort, time_filter=time_filter, after=after
                )
            except Exception as exc:  # noqa: BLE001 - move on to the next sort
                print(f"  [{sort}/{time_filter}] page {page}: failed ({exc})")
                break
            if not posts:
                break
            new_count = _store_posts(conn, posts)
            sort_new += new_count
            total_in_db += new_count
            after = f"t3_{posts[-1].post_id}"
            empty_pages = empty_pages + 1 if new_count == 0 else 0
            if empty_pages >= _MAX_EMPTY_PAGES or total_in_db >= target_count:
                break
        print(f"[{sort}/{time_filter}]: +{sort_new} new posts (total in db: {total_in_db})")

    client.close()
    counts = Counter(
        row[0]
        for row in conn.execute("SELECT subreddit FROM classifications").fetchall()
    )
    print(f"\nTotal: {sum(counts.values())} posts across {len(counts)} subreddits:")
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
    total = len(rows)
    print(f"\nClassifying {total} posts with Ollama ({settings.ollama_model})...")
    start = time.monotonic()
    leads_found = 0
    for i, (post_id, subreddit, title, permalink, author, created_utc, body_snippet) in enumerate(
        rows, start=1
    ):
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
        if result.score >= settings.min_llm_score:
            leads_found += 1
            print(f"[ollama] LEAD r/{subreddit} {post_id} score={result.score:.2f} {result.reason}")
        if i % 100 == 0 or i == total:
            elapsed = time.monotonic() - start
            rate = i / elapsed if elapsed else 0
            eta_min = (total - i) / rate / 60 if rate else 0
            print(
                f"  ...{i}/{total} classified ({leads_found} leads so far, "
                f"{rate:.2f}/s, ETA {eta_min:.0f} min)"
            )


if __name__ == "__main__":
    target_count = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
    settings = Settings()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    conn.commit()
    fetch_and_store(conn, settings, target_count)
    classify_with_ollama(conn, settings)
    conn.close()
    print(f"\nDone. Benchmark data in {DB_PATH}")
