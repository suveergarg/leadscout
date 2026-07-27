from __future__ import annotations

import typer
import uvicorn

from leadscout.classify import build_classifier
from leadscout.config import Settings
from leadscout.dashboard import create_app
from leadscout.models import RedditPost
from leadscout.reddit_client import build_reddit_client
from leadscout.runner import run_loop
from leadscout.scraper import poll_once
from leadscout.store import SqliteStore

app = typer.Typer(help="leadscout — reddit lead-gen scanner for availwatch")


@app.command()
def run() -> None:
    """Long-running loop: poll all subreddits on a fixed interval."""
    run_loop(Settings())


@app.command("poll-once")
def poll_once_cmd() -> None:
    """Single pass over all configured subreddits, then exit."""
    settings = Settings()
    client = build_reddit_client(settings)
    classifier = build_classifier(settings)
    store = SqliteStore(settings.db_path)
    try:
        found = poll_once(settings, client, classifier, store)
        typer.echo(f"{found} new lead(s)")
    finally:
        client.close()


@app.command("backfill-replies")
def backfill_replies() -> None:
    """Draft a suggested reply for any existing lead that doesn't have one yet - leads
    stored before suggest_reply() existed, or ones where drafting failed at the time."""
    settings = Settings()
    classifier = build_classifier(settings)
    store = SqliteStore(settings.db_path)
    leads = [lead for lead in store.list_leads(include_dismissed=True) if not lead.suggested_reply]
    for lead in leads:
        post = RedditPost(
            post_id=lead.post_id,
            subreddit=lead.subreddit,
            title=lead.title,
            permalink=lead.permalink,
            author=lead.author,
            created_utc=lead.created_utc,
            body_snippet=lead.body_snippet,
        )
        try:
            reply = classifier.suggest_reply(post)
        except Exception as exc:  # noqa: BLE001 - report and move on to the next lead
            typer.echo(f"failed to draft a reply for {lead.post_id}: {exc}")
            continue
        if reply:
            store.update_suggested_reply(lead.post_id, reply)
    typer.echo(f"drafted replies for {len(leads)} lead(s)")


@app.command()
def serve() -> None:
    """Serve the local leads dashboard (127.0.0.1 only)."""
    settings = Settings()
    store = SqliteStore(settings.db_path)
    app_ = create_app(store, subreddits=settings.subreddits)
    uvicorn.run(app_, host=settings.dashboard_host, port=settings.dashboard_port)


if __name__ == "__main__":
    app()
