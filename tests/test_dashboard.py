from __future__ import annotations

from fastapi.testclient import TestClient

from leadscout.dashboard import create_app
from leadscout.models import Lead
from leadscout.store import SqliteStore


def _lead(post_id: str = "abc123", status: str = "new") -> Lead:
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
        status=status,
        first_seen="2026-07-25T00:00:00+00:00",
    )


def test_index_lists_new_lead(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "leadscout.db"))
    store.add_lead(_lead())
    client = TestClient(create_app(store))
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Sold out instantly" in resp.text


def test_dismiss_removes_from_default_view(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "leadscout.db"))
    store.add_lead(_lead())
    client = TestClient(create_app(store))
    resp = client.post("/dismiss/abc123", follow_redirects=True)
    assert resp.status_code == 200
    assert "No leads yet" in resp.text
