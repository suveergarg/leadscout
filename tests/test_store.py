from __future__ import annotations

from leadscout.models import Lead
from leadscout.store import SqliteStore


def _lead(post_id: str = "abc123") -> Lead:
    return Lead(
        post_id=post_id,
        subreddit="CAMPING",
        title="Sold out instantly",
        permalink="https://www.reddit.com/r/CAMPING/comments/abc123/",
        author="camper1",
        created_utc=1700000000.0,
        body_snippet="Refreshing all day",
        keyword_matched="sold out",
        llm_score=0.8,
        llm_reason="frustrated, wants alerts",
        first_seen="2026-07-25T00:00:00+00:00",
    )


def test_add_and_list_lead(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "leadscout.db"))
    store.add_lead(_lead())
    leads = store.list_leads()
    assert len(leads) == 1
    assert leads[0].post_id == "abc123"


def test_seen_dedup(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "leadscout.db"))
    assert not store.seen("abc123")
    store.add_lead(_lead())
    assert store.seen("abc123")


def test_dismiss_drops_from_default_view(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "leadscout.db"))
    store.add_lead(_lead())
    store.dismiss("abc123")
    assert store.list_leads() == []
    assert len(store.list_leads(include_dismissed=True)) == 1
