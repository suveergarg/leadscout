from __future__ import annotations

import sqlite3
from typing import Protocol

from leadscout.models import Lead


class Store(Protocol):
    def seen(self, post_id: str) -> bool: ...
    def mark_seen(
        self, post_id: str, subreddit: str, title: str, llm_score: float, llm_reason: str,
        classified_at: str,
    ) -> None: ...
    def add_lead(self, lead: Lead) -> None: ...
    def list_leads(self, include_dismissed: bool = False) -> list[Lead]: ...
    def dismiss(self, post_id: str) -> None: ...
    def mark_responded(self, post_id: str) -> None: ...
    def subreddit_stats(self) -> dict[str, dict[str, int]]: ...
    def update_suggested_reply(self, post_id: str, reply: str) -> None: ...


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, coltype: str) -> None:
    """Additive schema migration - a fresh CREATE TABLE IF NOT EXISTS never reaches an
    already-existing db file, so new Lead fields need an explicit ALTER TABLE."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


class SqliteStore:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads (
                post_id TEXT PRIMARY KEY, subreddit TEXT, title TEXT, permalink TEXT,
                author TEXT, created_utc REAL, body_snippet TEXT, keyword_matched TEXT,
                llm_score REAL, llm_reason TEXT, status TEXT NOT NULL DEFAULT 'new',
                first_seen TEXT
            );
            -- Every post the LLM has ever classified, lead or not - `seen` checks this, not
            -- `leads`, so a post that scored below threshold is never reclassified on a later
            -- poll just because it's still in Reddit's `new` listing.
            CREATE TABLE IF NOT EXISTS seen_posts (
                post_id TEXT PRIMARY KEY, subreddit TEXT, title TEXT,
                llm_score REAL, llm_reason TEXT, classified_at TEXT
            );
            """
        )
        _ensure_column(self._conn, "leads", "suggested_reply", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(self._conn, "leads", "responded", "INTEGER NOT NULL DEFAULT 0")
        self._conn.commit()

    def seen(self, post_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM seen_posts WHERE post_id = ?", (post_id,)
        ).fetchone()
        return row is not None

    def mark_seen(
        self, post_id: str, subreddit: str, title: str, llm_score: float, llm_reason: str,
        classified_at: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO seen_posts
                (post_id, subreddit, title, llm_score, llm_reason, classified_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (post_id, subreddit, title, llm_score, llm_reason, classified_at),
        )
        self._conn.commit()

    def add_lead(self, lead: Lead) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO leads
                (post_id, subreddit, title, permalink, author, created_utc, body_snippet,
                 keyword_matched, llm_score, llm_reason, status, first_seen, suggested_reply,
                 responded)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead.post_id,
                lead.subreddit,
                lead.title,
                lead.permalink,
                lead.author,
                lead.created_utc,
                lead.body_snippet,
                lead.keyword_matched,
                lead.llm_score,
                lead.llm_reason,
                lead.status,
                lead.first_seen,
                lead.suggested_reply,
                int(lead.responded),
            ),
        )
        self._conn.commit()

    def list_leads(self, include_dismissed: bool = False) -> list[Lead]:
        query = "SELECT * FROM leads"
        if not include_dismissed:
            query += " WHERE status != 'dismissed'"
        query += " ORDER BY created_utc DESC"
        rows = self._conn.execute(query).fetchall()
        return [Lead(**dict(row)) for row in rows]

    def mark_responded(self, post_id: str) -> None:
        self._conn.execute("UPDATE leads SET responded = 1 WHERE post_id = ?", (post_id,))
        self._conn.commit()

    def update_suggested_reply(self, post_id: str, reply: str) -> None:
        self._conn.execute(
            "UPDATE leads SET suggested_reply = ? WHERE post_id = ?", (reply, post_id)
        )
        self._conn.commit()

    def subreddit_stats(self) -> dict[str, dict[str, int]]:
        """{subreddit: {"scanned": N, "leads": M}} for every subreddit with at least one
        scanned post or lead recorded - callers merge in monitored-but-quiet subreddits."""
        stats: dict[str, dict[str, int]] = {}
        for sub, count in self._conn.execute(
            "SELECT subreddit, COUNT(*) FROM seen_posts GROUP BY subreddit"
        ).fetchall():
            stats.setdefault(sub, {"scanned": 0, "leads": 0})["scanned"] = count
        for sub, count in self._conn.execute(
            "SELECT subreddit, COUNT(*) FROM leads GROUP BY subreddit"
        ).fetchall():
            stats.setdefault(sub, {"scanned": 0, "leads": 0})["leads"] = count
        return stats

    def dismiss(self, post_id: str) -> None:
        self._conn.execute("UPDATE leads SET status = 'dismissed' WHERE post_id = ?", (post_id,))
        self._conn.commit()
