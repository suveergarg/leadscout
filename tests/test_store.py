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
        suggested_reply="sounds rough, availwatch might help",
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
    store.mark_seen("abc123", "CAMPING", "Sold out instantly", 0.8, "frustrated", "2026-07-25T00:00:00+00:00")
    assert store.seen("abc123")


def test_mark_seen_dedupes_a_post_that_never_becomes_a_lead(tmp_path) -> None:
    """The real bug this fixes: a below-threshold post must be graded once, not every poll
    cycle it remains in Reddit's `new` listing. add_lead() is never called for it here."""
    store = SqliteStore(str(tmp_path / "leadscout.db"))
    store.mark_seen("xyz789", "CAMPING", "Best tent for winter?", 0.05, "gear question",
                     "2026-07-25T00:00:00+00:00")
    assert store.seen("xyz789")
    assert store.list_leads() == []


def test_dismiss_drops_from_default_view(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "leadscout.db"))
    store.add_lead(_lead())
    store.dismiss("abc123")
    assert store.list_leads() == []
    assert len(store.list_leads(include_dismissed=True)) == 1


def test_add_lead_stores_suggested_reply(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "leadscout.db"))
    store.add_lead(_lead())
    lead = store.list_leads()[0]
    assert lead.suggested_reply == "sounds rough, availwatch might help"
    assert lead.responded is False


def test_mark_responded(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "leadscout.db"))
    store.add_lead(_lead())
    store.mark_responded("abc123")
    assert store.list_leads()[0].responded is True


def test_subreddit_stats_counts_scanned_and_leads(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "leadscout.db"))
    store.mark_seen("s1", "CAMPING", "t1", 0.1, "reason", "2026-07-25T00:00:00+00:00")
    store.mark_seen("s2", "CAMPING", "t2", 0.1, "reason", "2026-07-25T00:00:00+00:00")
    store.mark_seen("abc123", "CAMPING", "Sold out instantly", 0.8, "reason",
                     "2026-07-25T00:00:00+00:00")
    store.add_lead(_lead())
    stats = store.subreddit_stats()
    assert stats == {"CAMPING": {"scanned": 3, "leads": 1}}
