from __future__ import annotations

from datetime import datetime, timezone

from leadscout.classify import Classifier
from leadscout.config import Settings
from leadscout.keywords import matched_phrase
from leadscout.models import Lead
from leadscout.reddit_client import RedditFeed, combined_subreddits
from leadscout.store import Store


def poll_once(settings: Settings, client: RedditFeed, classifier: Classifier, store: Store) -> int:
    """One pass over every configured subreddit, fetched as a single combined
    multireddit request (see reddit_client.combined_subreddits) rather than one
    request per subreddit - the same cost as fetching just one, which matters a lot
    under RssRedditClient's tight anonymous rate limit. Trade-off: a fetch failure now
    takes down the whole pass instead of just one subreddit.

    No keyword pre-filter: every unseen post is classified directly. matched_phrase()
    is still recorded on the lead (may be None) for comparison against the old
    keyword-gated behavior, not used to skip classification."""
    combined = combined_subreddits(settings.subreddits)
    try:
        posts = client.new_posts(combined, limit=settings.fetch_limit)
    except Exception as exc:  # noqa: BLE001 - report and skip; nothing fetched this pass
        print(f"leadscout: failed to fetch combined feed: {exc}")
        return 0

    new_leads = 0
    for post in posts:
        if store.seen(post.post_id):
            continue
        phrase = matched_phrase(post.title, post.body_snippet)
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
