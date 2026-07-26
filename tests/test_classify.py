from __future__ import annotations

from leadscout.classify import KeywordOnlyClassifier, build_classifier
from leadscout.config import Settings
from leadscout.models import RedditPost


def _post() -> RedditPost:
    return RedditPost(
        post_id="abc123",
        subreddit="CAMPING",
        title="Sold out instantly, any tool to get alerted?",
        permalink="https://www.reddit.com/r/CAMPING/comments/abc123/",
        author="camper1",
        created_utc=1700000000.0,
        body_snippet="Refreshing recreation.gov all day, no luck.",
    )


def test_keyword_only_classifier_returns_flat_score() -> None:
    result = KeywordOnlyClassifier().classify(_post())
    assert 0.0 < result.score <= 1.0
    assert result.reason


def test_build_classifier_falls_back_to_keyword_only_with_no_backend() -> None:
    settings = Settings(ollama_url=None, anthropic_api_key=None)
    classifier = build_classifier(settings)
    assert isinstance(classifier, KeywordOnlyClassifier)
