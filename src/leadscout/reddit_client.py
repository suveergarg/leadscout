from __future__ import annotations

import html
import re
import time
from datetime import datetime, timezone
from typing import Any, Protocol
from xml.etree import ElementTree

import httpx

from leadscout.config import Settings
from leadscout.models import RedditPost

_SNIPPET_LEN = 300


class RedditFeed(Protocol):
    """Common interface poll_once/run_loop depend on — satisfied by both the PRAW-backed
    RedditClient and the no-auth RssRedditClient fallback."""

    def new_posts(self, subreddit: str, limit: int = 25) -> list[RedditPost]: ...
    def close(self) -> None: ...


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


_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
_TAG_RE = re.compile(r"<[^>]+>")
_SELFTEXT_RE = re.compile(r"<!-- SC_OFF -->(.*?)<!-- SC_ON -->", re.DOTALL)


def _body_snippet(content_html: str) -> str:
    """Reddit's RSS `content` field wraps selftext in SC_OFF/SC_ON markers, followed by a
    "submitted by .../[link]/[comments]" footer we don't want. Link-only posts have no
    selftext div at all."""
    match = _SELFTEXT_RE.search(content_html)
    if not match:
        return ""
    text = html.unescape(_TAG_RE.sub(" ", match.group(1)))
    return " ".join(text.split())[:_SNIPPET_LEN]


def _parse_entry(entry: ElementTree.Element, subreddit: str) -> RedditPost:
    def find_text(path: str) -> str:
        el = entry.find(path, _ATOM_NS)
        return el.text or "" if el is not None else ""

    entry_id = find_text("a:id")
    post_id = entry_id.split("_", 1)[1] if "_" in entry_id else entry_id
    link_el = entry.find("a:link", _ATOM_NS)
    permalink = link_el.get("href", "") if link_el is not None else ""
    author = find_text("a:author/a:name").removeprefix("/u/") or "[deleted]"
    published = find_text("a:published") or find_text("a:updated")
    created_utc = datetime.fromisoformat(published).astimezone(timezone.utc).timestamp()

    # Multireddit feeds (r/sub1+sub2/...) tag each entry with its real source via
    # <category label="r/..."/>; single-subreddit feeds may omit it, so fall back to
    # the subreddit the caller requested.
    category_el = entry.find("a:category", _ATOM_NS)
    entry_subreddit = (
        category_el.get("label", "").removeprefix("r/") if category_el is not None else ""
    )

    return RedditPost(
        post_id=post_id,
        subreddit=entry_subreddit or subreddit,
        title=find_text("a:title"),
        permalink=permalink,
        author=author,
        created_utc=created_utc,
        body_snippet=_body_snippet(find_text("a:content")),
    )


class RssRedditClient:
    """Fallback for when a PRAW OAuth app is pending/unavailable (Reddit's 2026 Responsible
    Builder Policy gates new app approval behind a manual, multi-week review). Reads a
    subreddit's public `new` Atom feed directly — no credentials, no approval needed, since
    this endpoint was never part of the priced/gated API surface. Unlike `.json` scraping
    (blocked outright, see Settings.reddit_client_id docstring), `.rss` remains open.

    Best-effort only, and tightly rate-limited: confirmed live, the anonymous per-IP bucket
    grants about one request before `x-ratelimit-remaining` drops to 0, refilling after the
    `x-ratelimit-reset` seconds that response reports. new_posts() honors those headers and
    blocks until the bucket refills rather than guessing a fixed delay — a full pass over
    ~10 subreddits will take several minutes, but that's still comfortably inside a 15-minute
    poll interval. Swap back to RedditClient once a PRAW app is approved.
    """

    def __init__(self, user_agent: str) -> None:
        self._client = httpx.Client(headers={"User-Agent": user_agent}, timeout=15)
        self._sleep_until: float | None = None

    def new_posts(self, subreddit: str, limit: int = 25) -> list[RedditPost]:
        self._wait_for_rate_limit()
        resp = self._client.get(f"https://www.reddit.com/r/{subreddit}/new/.rss?limit={limit}")
        self._record_rate_limit(resp.headers)
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.text)
        entries = root.findall("a:entry", _ATOM_NS)[:limit]
        return [_parse_entry(entry, subreddit) for entry in entries]

    def _wait_for_rate_limit(self) -> None:
        if self._sleep_until is None:
            return
        remaining = self._sleep_until - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)

    def _record_rate_limit(self, headers: httpx.Headers) -> None:
        try:
            remaining = float(headers["x-ratelimit-remaining"])
            reset = float(headers["x-ratelimit-reset"])
        except (KeyError, ValueError):
            self._sleep_until = None
            return
        self._sleep_until = time.monotonic() + reset if remaining < 1 else None

    def close(self) -> None:
        self._client.close()


def build_reddit_client(settings: Settings) -> RedditFeed:
    """Application-only (client_credentials) OAuth — read-only, no Reddit user account
    required: PRAW enters read-only mode automatically when no username/password is given.
    Falls back to RssRedditClient when no Reddit app credentials are configured."""
    if not (settings.reddit_client_id and settings.reddit_client_secret):
        return RssRedditClient(settings.user_agent)

    import praw

    reddit = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.user_agent,
    )
    return RedditClient(reddit)
