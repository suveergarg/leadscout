from __future__ import annotations

from typing import Any, Protocol

from leadscout.config import Settings
from leadscout.models import RedditPost

_SNIPPET_LEN = 300


class RedditSource(Protocol):
    """The slice of praw.Reddit's interface RedditClient needs — lets tests inject a fake
    without a real Reddit app or network access."""

    def subreddit(self, name: str) -> Any: ...


class RedditClient:
    """Wraps a PRAW `Reddit` instance (or test double) to yield normalized RedditPosts."""

    def __init__(self, reddit: RedditSource) -> None:
        self._reddit = reddit

    def new_posts(self, subreddit: str, limit: int = 25) -> list[RedditPost]:
        posts = []
        for submission in self._reddit.subreddit(subreddit).new(limit=limit):
            posts.append(
                RedditPost(
                    post_id=submission.id,
                    subreddit=subreddit,
                    title=submission.title,
                    permalink=f"https://www.reddit.com{submission.permalink}",
                    author=str(submission.author) if submission.author else "[deleted]",
                    created_utc=submission.created_utc,
                    body_snippet=(submission.selftext or "")[:_SNIPPET_LEN],
                )
            )
        return posts

    def close(self) -> None:
        pass


def build_reddit_client(settings: Settings) -> RedditClient:
    """Application-only (client_credentials) OAuth — read-only, no Reddit user account
    required: PRAW enters read-only mode automatically when no username/password is given."""
    import praw

    reddit = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.user_agent,
    )
    return RedditClient(reddit)
