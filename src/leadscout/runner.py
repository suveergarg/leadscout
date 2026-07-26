from __future__ import annotations

import time

from leadscout.classify import build_classifier
from leadscout.config import Settings
from leadscout.reddit_client import build_reddit_client
from leadscout.scraper import poll_once
from leadscout.store import SqliteStore


def run_loop(settings: Settings) -> None:
    """Long-running loop: poll all subreddits, sleep, repeat. Ctrl-C to stop."""
    client = build_reddit_client(settings)
    classifier = build_classifier(settings)
    store = SqliteStore(settings.db_path)
    try:
        while True:
            found = poll_once(settings, client, classifier, store)
            print(f"leadscout: pass complete, {found} new lead(s)")
            time.sleep(settings.poll_interval_seconds)
    finally:
        client.close()
