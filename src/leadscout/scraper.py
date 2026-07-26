from __future__ import annotations

from datetime import datetime, timezone

from leadscout.classify import Classifier
from leadscout.config import Settings
from leadscout.keywords import matched_phrase
from leadscout.models import Lead
from leadscout.reddit_client import RedditFeed
from leadscout.store import Store


def poll_once(settings: Settings, client: RedditFeed, classifier: Classifier, store: Store) -> int:
    """One pass over all configured subreddits. Returns count of new leads stored.
    A single subreddit's fetch failure is logged and skipped, not fatal to the pass."""
    new_leads = 0
    for subreddit in settings.subreddits:
        try:
            posts = client.new_posts(subreddit, limit=settings.posts_per_subreddit)
        except Exception as exc:  # noqa: BLE001 - one bad subreddit must not kill the pass
            print(f"leadscout: failed to fetch r/{subreddit}: {exc}")
            continue
        for post in posts:
            if store.seen(post.post_id):
                continue
            phrase = matched_phrase(post.title, post.body_snippet)
            if phrase is None:
                continue
            classification = classifier.classify(post)
            if classification.score < settings.min_llm_score:
                continue
            store.add_lead(
                Lead(
                    **post.model_dump(),
                    keyword_matched=phrase,
                    llm_score=classification.score,
                    llm_reason=classification.reason,
                    first_seen=datetime.now(timezone.utc).isoformat(),
                )
            )
            new_leads += 1
    return new_leads
