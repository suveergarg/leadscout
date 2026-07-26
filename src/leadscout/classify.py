from __future__ import annotations

from typing import Any, Protocol

import httpx

from leadscout.config import Settings
from leadscout.models import Classification, RedditPost

_SYSTEM = """You screen Reddit posts for leads for availwatch, a tool that alerts people the
moment a sold-out campsite/permit/timed-entry slot opens up.

Given a post's title and body, decide whether the author is plausibly frustrated with hunting
for availability (sold-out sites, manually refreshing, asking for a tool/alert) — a real signal
this person might want availwatch — versus general camping chatter, trip reports, gear
questions, or unrelated content.

Return score (0.0-1.0, how strong the signal is) and reason (one short sentence why)."""


class Classifier(Protocol):
    def classify(self, post: RedditPost) -> Classification: ...


def _prompt(post: RedditPost) -> str:
    return f"Subreddit: r/{post.subreddit}\nTitle: {post.title}\nBody: {post.body_snippet}"


def _extract_json(content: str) -> str:
    content = content.strip()
    if "```" in content:
        content = content.split("```")[1].removeprefix("json").strip()
    start, end = content.find("{"), content.rfind("}")
    return content[start : end + 1] if start != -1 and end > start else content


class OllamaClassifier:
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def classify(self, post: RedditPost) -> Classification:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _prompt(post)},
            ],
            "format": Classification.model_json_schema(),
            "options": {"temperature": 0},
        }
        resp = httpx.post(f"{self._base_url}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
        return Classification.model_validate_json(_extract_json(content))


class ClaudeClassifier:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    def classify(self, post: RedditPost) -> Classification:
        resp = self._client.messages.parse(
            model=self._model,
            max_tokens=256,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _prompt(post)}],
            output_format=Classification,
        )
        return resp.parsed_output


class KeywordOnlyClassifier:
    """No LLM backend configured — every keyword-matched post scores a flat mid-confidence
    value so it still surfaces on the dashboard for a human to judge."""

    _SCORE = 0.5

    def classify(self, post: RedditPost) -> Classification:  # noqa: ARG002
        return Classification(score=self._SCORE, reason="keyword match only (no LLM backend)")


def build_classifier(settings: Settings) -> Classifier:
    if settings.ollama_url:
        return OllamaClassifier(settings.ollama_url, settings.ollama_model)
    if settings.anthropic_api_key:
        import anthropic

        return ClaudeClassifier(
            anthropic.Anthropic(api_key=settings.anthropic_api_key), settings.classify_model
        )
    return KeywordOnlyClassifier()
