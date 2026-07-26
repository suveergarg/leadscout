from __future__ import annotations

import typer
import uvicorn

from leadscout.classify import build_classifier
from leadscout.config import Settings
from leadscout.dashboard import create_app
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


@app.command()
def serve() -> None:
    """Serve the local leads dashboard (127.0.0.1 only)."""
    settings = Settings()
    store = SqliteStore(settings.db_path)
    uvicorn.run(create_app(store), host=settings.dashboard_host, port=settings.dashboard_port)


if __name__ == "__main__":
    app()
