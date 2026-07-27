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

_REPLY_SYSTEM = """You draft a short Reddit reply for the person who built S'more Alerts
(smorealerts.com), a tool that alerts people the moment a sold-out campsite/permit/timed-entry
slot opens up.

Reddit's self-promotion rules require disclosing a vested interest whenever you mention your own
product - never write as if you're an uninvolved stranger who "happens to know about a tool."
Write a brief, natural reply (2-4 sentences) with two parts:
1. Genuinely useful, specific advice for their situation (a concrete tip, alternative approach,
   or resource) - the reply must stand on its own as helpful even if the reader ignores the
   product mention entirely. This is not optional filler before the pitch.
2. A plain, honest disclosure that you built S'more Alerts and it might help with exactly this,
   e.g. "I actually built S'more Alerts (smorealerts.com) for this" - stated openly, not implied.

No hyperlinked/markdown links, no exclamation-heavy enthusiasm, no emoji, no hard sell. If you
don't have any genuinely useful advice to offer beyond the product mention, return an empty
string rather than padding it out - a plug with no real help is exactly the spam Reddit's rules
are aimed at. If the post barely warrants a reply, keep it short and low-key.

Return only the reply text, nothing else - no preamble, no quotes around it."""


class Classifier(Protocol):
    def classify(self, post: RedditPost) -> Classification: ...
    def suggest_reply(self, post: RedditPost) -> str: ...


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

    def suggest_reply(self, post: RedditPost) -> str:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": _REPLY_SYSTEM},
                {"role": "user", "content": _prompt(post)},
            ],
            "options": {"temperature": 0.4},
        }
        resp = httpx.post(f"{self._base_url}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()


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

    def suggest_reply(self, post: RedditPost) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=300,
            system=_REPLY_SYSTEM,
            messages=[{"role": "user", "content": _prompt(post)}],
        )
        return next((b.text for b in resp.content if b.type == "text"), "").strip()


class KeywordOnlyClassifier:
    """No LLM backend configured — every keyword-matched post scores a flat mid-confidence
    value so it still surfaces on the dashboard for a human to judge."""

    _SCORE = 0.5

    def classify(self, post: RedditPost) -> Classification:  # noqa: ARG002
        return Classification(score=self._SCORE, reason="keyword match only (no LLM backend)")

    def suggest_reply(self, post: RedditPost) -> str:  # noqa: ARG002
        return ""  # no LLM backend to draft a genuine reply with


def build_classifier(settings: Settings) -> Classifier:
    if settings.ollama_url:
        return OllamaClassifier(settings.ollama_url, settings.ollama_model)
    if settings.anthropic_api_key:
        import anthropic

        return ClaudeClassifier(
            anthropic.Anthropic(api_key=settings.anthropic_api_key), settings.classify_model
        )
    return KeywordOnlyClassifier()
