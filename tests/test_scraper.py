from __future__ import annotations

from leadscout.classify import Classifier
from leadscout.models import Classification, RedditPost
from leadscout.scraper import poll_once
from leadscout.store import SqliteStore


class _FakeClient:
    def __init__(self, posts: list[RedditPost]) -> None:
        self._posts = posts

    def new_posts(self, subreddit: str, limit: int = 25) -> list[RedditPost]:
        return self._posts


class _FakeClassifier(Classifier):
    def __init__(self, score: float) -> None:
        self._score = score

    def classify(self, post: RedditPost) -> Classification:
        return Classification(score=self._score, reason="fake")


def _post(post_id: str, title: str, body: str = "") -> RedditPost:
    return RedditPost(
        post_id=post_id,
        subreddit="CAMPING",
        title=title,
        permalink=f"https://www.reddit.com/r/CAMPING/comments/{post_id}/",
        author="camper1",
        created_utc=1700000000.0,
        body_snippet=body,
    )


def test_poll_once_stores_matched_high_score_lead(settings) -> None:
    posts = [_post("a1", "Site was sold out in minutes")]
    store = SqliteStore(settings.db_path)
    found = poll_once(settings, _FakeClient(posts), _FakeClassifier(0.9), store)
    assert found == 1
    assert len(store.list_leads()) == 1


def test_poll_once_skips_below_score_threshold(settings) -> None:
    posts = [_post("a2", "Site was sold out in minutes")]
    store = SqliteStore(settings.db_path)
    found = poll_once(settings, _FakeClient(posts), _FakeClassifier(0.1), store)
    assert found == 0
    assert store.list_leads() == []


def test_poll_once_stores_high_score_lead_with_no_keyword_match(settings) -> None:
    """No keyword pre-filter: a post with no matched phrase still gets classified
    and stored if the LLM scores it highly. keyword_matched is recorded as None."""
    posts = [_post("a3", "Best tent for winter camping?")]
    store = SqliteStore(settings.db_path)
    found = poll_once(settings, _FakeClient(posts), _FakeClassifier(0.9), store)
    assert found == 1
    assert store.list_leads()[0].keyword_matched is None


def test_poll_once_skips_already_seen(settings) -> None:
    posts = [_post("a4", "Site was sold out in minutes")]
    store = SqliteStore(settings.db_path)
    poll_once(settings, _FakeClient(posts), _FakeClassifier(0.9), store)
    found_again = poll_once(settings, _FakeClient(posts), _FakeClassifier(0.9), store)
    assert found_again == 0
    assert len(store.list_leads()) == 1


def test_poll_once_returns_zero_on_fetch_error(settings) -> None:
    """poll_once now fetches every subreddit as a single combined request, so a fetch
    failure means the whole pass returns nothing this cycle - there's no longer a
    per-subreddit loop to fall back to the next entry in."""

    class _FailingClient:
        def new_posts(self, subreddit: str, limit: int = 25) -> list[RedditPost]:
            raise RuntimeError("boom")

    store = SqliteStore(settings.db_path)
    found = poll_once(settings, _FailingClient(), _FakeClassifier(0.9), store)
    assert found == 0
