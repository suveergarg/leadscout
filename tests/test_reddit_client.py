from __future__ import annotations

from types import SimpleNamespace

from leadscout.config import Settings
from leadscout.reddit_client import RedditClient, RssRedditClient, build_reddit_client


class _FakeSubredditFeed:
    def __init__(self, submissions: list) -> None:
        self._submissions = submissions

    def new(self, limit: int = 25):
        return iter(self._submissions[:limit])


class _FakeReddit:
    def __init__(self, submissions: list) -> None:
        self._submissions = submissions

    def subreddit(self, name: str) -> _FakeSubredditFeed:
        return _FakeSubredditFeed(self._submissions)


def _submission(**overrides) -> SimpleNamespace:
    defaults = dict(
        id="abc123",
        title="Any way to get alerted when a site opens?",
        permalink="/r/CAMPING/comments/abc123/title/",
        author="camper1",  # real praw Redditor objects stringify to the username too
        created_utc=1700000000.0,
        selftext="Sold out the second it went live, so frustrating.",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_new_posts_parses_submissions() -> None:
    client = RedditClient(_FakeReddit([_submission()]))
    posts = client.new_posts("CAMPING", limit=25)
    assert len(posts) == 1
    post = posts[0]
    assert post.post_id == "abc123"
    assert post.subreddit == "CAMPING"
    assert post.permalink == "https://www.reddit.com/r/CAMPING/comments/abc123/title/"
    assert post.author == "camper1"
    assert "Sold out" in post.body_snippet


def test_new_posts_handles_deleted_author() -> None:
    client = RedditClient(_FakeReddit([_submission(author=None)]))
    posts = client.new_posts("CAMPING")
    assert posts[0].author == "[deleted]"


def test_new_posts_respects_limit() -> None:
    client = RedditClient(_FakeReddit([_submission(id="a"), _submission(id="b")]))
    posts = client.new_posts("CAMPING", limit=1)
    assert len(posts) == 1


def test_build_reddit_client_falls_back_to_rss_with_no_credentials() -> None:
    settings = Settings(reddit_client_id=None, reddit_client_secret=None)
    client = build_reddit_client(settings)
    assert isinstance(client, RssRedditClient)


def test_build_reddit_client_uses_praw_with_credentials() -> None:
    settings = Settings(reddit_client_id="id", reddit_client_secret="secret")
    client = build_reddit_client(settings)
    assert isinstance(client, RedditClient)
