from __future__ import annotations

import pytest

from leadscout.config import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        db_path=str(tmp_path / "leadscout.db"),
        subreddits=["CAMPING"],
        min_llm_score=0.4,
        ollama_url=None,
        anthropic_api_key=None,
    )
