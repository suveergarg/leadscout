from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SUBREDDITS = [
    "CAMPING",
    "RECREATIONdotgov",
    "Yosemite",
    "glamping",
    "vandwellers",
    "GlacierNationalPark",
    "nationalparks",
    "CampingandHiking",
    "RVLiving",
    "backpacking",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LEADSCOUT_", env_file=".env", extra="ignore", populate_by_name=True
    )

    db_path: str = "leadscout.db"
    subreddits: list[str] = Field(default_factory=lambda: list(DEFAULT_SUBREDDITS))
    poll_interval_seconds: int = 900
    # poll_once fetches every subreddit in one combined multireddit request (see
    # reddit_client.combined_subreddits), not one request per subreddit - confirmed
    # live that Reddit's RSS caps a response at 100 entries regardless of the limit
    # requested or how many subreddits are combined, so this is a hard ceiling, not a
    # per-subreddit budget.
    fetch_limit: int = 100
    min_llm_score: float = 0.4
    # No-auth .json scraping is blocked outright by Reddit's edge (confirmed: 403 regardless
    # of network/UA) — read access goes through PRAW application-only OAuth instead. Register
    # a "script" app at reddit.com/prefs/apps for client_id/client_secret (no username/password
    # needed for read-only access).
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    user_agent: str = "leadscout/0.1 (personal lead-gen tool for availwatch; contact suveer@machines.run)"
    ollama_url: str | None = None
    ollama_model: str = "llama3.2:3b"
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    classify_model: str = "claude-opus-4-8"
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8100
